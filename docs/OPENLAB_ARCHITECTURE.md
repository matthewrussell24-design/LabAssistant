# OpenLab Chromatography Support

Phase 8 teaches LabAssistant its first chromatography "language": the Agilent
OpenLab CDS `.olax` archive. This document describes what an OpenLab experiment
*is*, how it maps into LabAssistant's Experiment → Observation → Measurement
model, how the first importer works, and what remains unknown.

> **Validation status.** The structural description below is based on Agilent
> OpenLab CDS 2.x conventions and on defensive parsing of archive contents.
> On July 8, 2026, the two real files were briefly available from
> `/Volumes/ESD-USB`. Direct inspection confirmed the outer archive layout and
> several nested package types before the USB volume unmounted. The importer is
> tested against synthetic and real-shape `.olax` fixtures that reproduce those
> observed structures. Sections marked **UNKNOWN** still need confirmation from
> a complete second pass over the real files. The importer is written to
> *report* what it finds rather than to assume, so it degrades gracefully when
> reality differs.

## 1. What Is an OpenLab Experiment?

An OpenLab `.olax` file is not a single measurement. It is a **container for a
whole analytical run** — the chromatography equivalent of a lab notebook page
for one sequence of injections.

Conceptually an OpenLab experiment is organized like this:

- A **Sequence** is the top-level unit of work: an ordered list of injections
  run on one instrument under one acquisition method (or a small set of
  methods). It carries metadata such as sequence name, operator, instrument, and
  creation time.
- Each **Injection** is one physical introduction of a sample onto the column.
  It has an injection order, a sample name, a vial/position, an acquisition
  method, and a run time. Injections are the natural "measurement" unit.
- Injections are typically a mix of **roles**: *blanks* (establish baseline and
  carryover), *standards/calibrators* (establish the quantitation curve), and
  *samples* (the material under study). A trustworthy sequence usually contains
  all three.
- Each injection produces one or more **detector signals** (chromatogram
  traces): DAD/UV absorbance channels, VWD/MWD, FID, MS/MSD, RI, etc. These are
  the raw time-vs-intensity data, stored in proprietary binary containers.
- After acquisition, a **processing (data-analysis) method** integrates each
  signal into a **peak table**: retention time, area, height, area%, tailing,
  resolution, and — when a calibration is applied — amount/concentration.
- The archive also carries **calibration** information, the **audit trail**
  (who did what, when; electronic-signature log), and method definitions.

So the right mental model is:

```text
OpenLab .olax  ≈  one experiment (a sequence)
   └── metadata: sequence name, operator, instrument, method(s)
   └── injections[]        (blanks, standards, samples)
        └── detector signals[]   (raw chromatogram traces, binary)
        └── peak table            (integrated + quantified results)
   └── acquisition method, processing method
   └── calibration
   └── audit trail
```

The scientific point of the archive is **not** "what files exist" but "what was
run, in what order, with what controls, and can the result be trusted and
quantified".

## 2. Conventional Archive Layout

`.olax` is a ZIP/Open-Packaging container. LabAssistant opens it read-only with
`zipfile` and classifies entries by name and extension. The observed files store
a single `.rslt` result package as URL-encoded Windows-style paths inside the
outer ZIP, for example:

```text
1290+HPLC-2026-07-02+12-23-00-04-00.rslt%5c...
```

The `%5c` segment is a backslash. LabAssistant normalizes that to `/` for
classification while preserving the original archive entry name as provenance.

The observed real files contained:

| Archive | Entries | Injections implied | Key package files |
| --- | ---: | ---: | --- |
| `HPLC Test 1.olax` | 25 | 8 | `.acaml`, `.mfx`, 8 `.dx`, 8 `.rx`, `.sqx`, 2 `.amx`, `.scml`, core properties |
| `HPLC test 2.olax` | 22 | 7 | `.acaml`, `.mfx`, 7 `.dx`, 7 `.rx`, `.sqx`, 1 `.amx`, `.scml`, core properties |

OpenLab CDS layouts group entries roughly as follows:

| Area | Typical entries | LabAssistant classifier |
| --- | --- | --- |
| Sequence / samples | `.sqx` nested packages, `Sequence*/*.xml`, `sequence.csv`, sample tables | `SEQUENCE_HINTS`, injection extraction |
| Result metadata | `.acaml` result XML, nested `.rx` `Base/InjectionACAML` | sequence metadata, injection extraction |
| Detector signals | observed `.dx` nested packages; conventional `*.CH`, `*.UV`, `*.MS`, `DAD1A.CH`, `VWD1A` | `SIGNAL_HINTS` → `detector_files` / `unknown_detector_files` |
| Peak / result tables | `*peak*`, `*result*`, `*compound*`, `*amount*` | `PEAK_TABLE_HINTS`; readable CSV/TSV tables are parsed into peaks |
| Acquisition method | observed `.amx`; conventional `*.m`, `acqmethod*`, `instrumentmethod*` | `ACQ_METHOD_HINTS` |
| Processing method | `*processing*`, `damethod*`, `*.pmd`, `*.rdl` | `PROCESSING_METHOD_HINTS` |
| Calibration | `*calibration*`, `*calib*`, `calcurve*` | `CALIBRATION_HINTS` |
| Audit / signatures | nested `.rx` `Base/AuditTrail`, `*audit*`, `signaturelog*` | `AUDIT_HINTS` |
| Instrument/sampler metadata | `.scml`, core-properties `.psmdcp`, `[Content_Types].xml` | metadata/provenance |

**UNKNOWN / to confirm against real files:**

- Complete folder hierarchy variants across OpenLab CDS 2.x exports (vs older
  ChemStation `.D` directories). The first two files used `.rslt%5c...` paths.
- The binary format of the detector signal containers (`.CH`/`.UV`/MS blobs) —
  observed `.dx` containers are nested ZIP packages and are currently
  **located but not decoded** into time/intensity arrays.
- Whether results are stored as an `ACAML` XML results container, a binary
  results store, or exported tables — this determines whether peak tables are
  readable without an OpenLab export step.
- Audit-trail schema and calibration-curve encoding.

## 3. Scientific Mapping (OpenLab → LabAssistant)

The mapping is designed so **any** future instrument can follow the same shape;
only the importer changes.

| OpenLab object | LabAssistant object | Notes |
| --- | --- | --- |
| Sequence | `Experiment` | Top-level, instrument-agnostic container |
| Injection | `ChromatographyMeasurement` | One analytical run (the "measurement") |
| Peak | `ChromatographyPeak` (measurement feature) | Retention time, area, tailing, role |
| Detector signal | measurement `source_files` + metadata | Raw trace, decoded later |
| Sample role (blank/std/sample) | `Observation` | "Blank injections detected", etc. |
| Missing/undecoded data | `Observation` (`data_completeness`) | "Missing peak table", "Unknown detector file" |
| Trend across injections/timepoints | `Observation` | Future: drift, degradation trends |
| Mass-balance assessment | `MassBalanceAssessment` → hypotheses/recommendations | Existing reasoning module |

The general principle: **raw evidence** becomes Measurements; **every discovery
about that evidence** becomes an Observation; **interpretation** consumes
Observations, never raw files.

## 4. Importer Design (`labassistant/importers/openlab_olax.py`)

The importer has two entry points:

- `inspect_openlab_olax(path) -> OpenLabOlaxImportResult` — low-level: opens the
  ZIP, enumerates entries, classifies signal/peak/method/audit/calibration
  files, opens nested OpenLab packages (`.rx`, `.dx`, `.sqx`, `.amx`) when they
  are ZIP containers, extracts injections from ACAML/XML/CSV/JSON/sequence
  tables, parses readable CSV/TSV peak tables into `ChromatographyPeak`
  features, builds `ChromatographyMeasurement` objects, and generates the
  Observation stream.
- `build_experiment_from_olax(path) -> Experiment` — the adapter entry point:
  wraps the result into an instrument-agnostic `Experiment` with measurements,
  observations, `unsupported_sections`, and provenance metadata.

Design choices:

- **No proprietary decoding is attempted where it is not required.** Detector
  signal packages (`.dx` in the observed files) are located and counted but not
  decoded to time/intensity arrays; the importer records them in
  `unsupported_sections` and emits an honest Observation instead of guessing.
- **Nested packages are first-class.** The observed `.rx`, `.dx`, `.sqx`, and
  `.amx` files are ZIP containers inside the outer `.olax`; readable nested XML
  parts such as `Base/InjectionACAML` are inspected without extracting anything
  to disk.
- **Readable peak exports are first-class evidence.** When OpenLab stores or
  exports peak/result tables as CSV or TSV, LabAssistant maps rows to
  `ChromatographyPeak` objects with retention time, area, area%, height,
  tailing, resolution, signal-to-noise, and integration bounds when columns are
  present. These peaks are attached to the matching injection by sample name.
- **Everything is heuristic-first and defensive.** Injections are recovered from
  structured metadata when present, and inferred from archive layout as a
  fallback. Unreadable/binary entries are skipped, not fatal.
- **Nothing is dropped silently.** Signal-like files with an unrecognized
  detector type surface as `unknown_detector_files` and an "Unknown detector
  file" Observation.

The companion command-line helper can be used once real archives are available:

```bash
scripts/inspect-olax path/to/run.olax
```

## 5. Observation Model (Part 4)

Every discovery becomes structured knowledge, not console output. Observations
carry `label`, `category`, `severity` (`review`/`watch`/`normal`/`info`),
`confidence`, `evidence`, optional `recommendation`, and provenance.

Two category conventions drive the reasoning layer:

- **Positive facts** use `category="chromatography_import"`: "OpenLab sequence
  loaded", "Injections found", "Blank injections detected", "Standards
  detected", "Sample injections detected", "Chromatogram signal available",
  "Peak table available", "Acquisition method available", "Audit trail
  available", "Calibration data available".
- **Gaps** use `category="data_completeness"`: "No injections found", "Missing
  peak table", "Unknown detector file", "Processing method missing". Gap
  severity encodes impact — `review` blocks interpretation, `watch` limits it.

This category convention is the contract every future importer follows so the
Investigator stays instrument-agnostic.

## 6. Scientific Investigator (`labassistant/investigator.py`, Part 5)

The Investigator is the first component of the reasoning layer. It **consumes
Observations only** — never raw files, never Measurements — and uses purely
deterministic rules (no LLM). It answers:

- **What happened?** — a summary of observation counts and highlights.
- **Is the experiment complete?** — false if any `data_completeness` gap exists.
- **Is anything missing?** — the list of gaps.
- **Can it be interpreted?** — `Yes` (evidence present, no blocker),
  `Partially` (watch-level gaps limit confidence), or `No` (a review-level gap
  blocks interpretation, or there is no substantive evidence).
- **What would improve confidence?** — deduplicated recommendations, gaps first.

Because it works off the Observation stream, the same Investigator already
reasons about DLS observations and will reason about any future instrument
without modification.

## 7. Assumptions, Unknowns, Future Work

**Assumptions**

- `.olax` is a readable ZIP/OPC container.
- Sequence/injection metadata is discoverable as XML/CSV/JSON or inferable from
  layout.
- Sample role can be guessed from sample-name conventions (blank/std/standard).

**Unknowns (need the real archives)**

- Detector signal binary formats and the results/ACAML container schema.
- Complete ACAML result schema, especially where integrated peak tables and
  quantitative results live.
- Audit-trail and calibration-curve encodings.
- Whether peak tables are present without an explicit OpenLab export.
- How OpenLab names multi-detector or multi-signal injections inside the real
  archives; current signal association uses injection order and sample-name
  matching when possible.

**Future work**

- Decode detector signals into time/intensity arrays for chromatogram plotting.
- Extend peak parsing beyond readable CSV/TSV exports and feed the existing
  mass-balance engine with parent loss vs impurity growth vs total-area
  conservation, recovery, unknown peaks, and retention shifts.
- Cross-technique mass balance: correlate HPLC "missing mass" with DLS
  aggregation observations (the hypothesis link already exists in
  `chromatography.mass_balance_hypotheses`).
- Trend Observations across injections, timepoints, and stability studies.

## 8. Instrument-Agnostic Vision

The architecture is built for the next thousand experiments, not these two
files. Adding an instrument means writing one importer that fills an
`Experiment` with Measurements and Observations using the shared category
conventions. DLS, HPLC, SEC, UV-Vis, ELISA, DSC, rheology, and stability studies
all plug into the same reasoning layer:

```text
[instrument file]  →  [importer]  →  Experiment { measurements, observations }
                                          │
                        Observations only ▼
                                   [Investigator]  → what happened / complete /
                                                     interpretable / confidence
                                   [Mass balance]  → hypotheses / recommendations
```

The intelligence is the product. Instruments are plugins. Experiments are
first-class. Measurements are building blocks. Observations are the shared
language between them.
