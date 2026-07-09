# LabAssistant Roadmap

This roadmap moves LabAssistant from a working Zetasizer/DLS workflow toward an
Experiment Intelligence Platform without breaking the current product.

## Current State

The current app already has a useful DLS workflow:

- Multi-file Zetasizer import preview.
- Lot grouping and `Measurement` merge.
- DLS summary, intensity distribution, and correlogram parsing.
- LabAssistant-derived particle-size metrics.
- Dual-angle aggregation screening.
- Experiment history, trend views, drift comparison, and similar-run search.
- A decision-first Streamlit dashboard.

This is the foundation. It should be protected while the architecture shifts
from file and measurement processing toward experiment lifecycle intelligence.

## Phase 1: Rename The Product Concepts

Goal: make the code and docs describe LabAssistant as a platform, while keeping
existing behavior unchanged.

- Treat "Decision Brief" as "Experiment Brief" in new docs and new code.
- Treat "Zetasizer importer" as one ingestion adapter.
- Treat DLS quality checks as particle-size quality assessment.
- Keep current UI labels stable unless changing them is low risk.
- Add docs that clearly separate instrument plugins from shared intelligence.

Status: documentation updated.

## Phase 2: Introduce Stable Domain Models

Goal: introduce the target hierarchy without forcing all current code to migrate
at once.

Preferred long-term model split:

```text
labassistant/models/
  workspace.py
  project.py
  experiment.py
  observation.py
  measurement.py
```

Near-term safe move:

- Keep `labassistant/models.py` working.
- Add lightweight `Workspace`, `Project`, `Experiment`, and `Observation`
  dataclasses in `models.py` first, rather than moving files immediately.
- Add an `Experiment` dataclass that contains experiment-level metadata,
  conditions, measurements, observations, reasoning results, historical context,
  and report references.
- Add an `Observation` dataclass with fields such as `label`, `category`,
  `evidence`, `source_type`, `source_id`, `confidence`, `severity`, and
  `created_by`.
- Add optional fields that are broadly useful across instruments:
  `technique`, `analyte`, `method_id`, `batch_id`, `formulation_id`,
  `replicate_id`, and richer `provenance`.
- Treat existing `Measurement` objects as evidence blocks inside an experiment.
- Add helper functions that derive initial observations from existing DLS
  warnings, derived metrics, dual-angle aggregation assessments, and
  reproducibility analyses.
- Avoid renaming existing fields that the UI and tests rely on.
- Add adapter helpers that can assemble current `Measurement` objects into an
  experiment envelope.

## Phase 3: Create An Ingestion Namespace

Goal: make instrument-specific parsing visibly separate from experiment
assembly and reasoning.

Preferred long-term shape:

```text
labassistant/ingestion/
  zetasizer.py
  hplc.py
  sec.py
  uvvis.py
```

Near-term safe move:

- Keep `labassistant/importers/dls.py` intact.
- Add `labassistant/ingestion/zetasizer.py` as a compatibility facade that calls
  the existing DLS importer.
- Keep the generic filtration CSV importer conservative: simple tabular
  measurements only, row-level warnings, no proprietary device assumptions.
- Preserve explicit experimental variables and orthogonal follow-up measurements
  in provenance so saved experiments can be rehydrated into editable state
  without mutating append-only history.
- Add an experiment assembly layer that groups parsed measurements by
  experiment context, not only by upload batch or lot.
- Gradually move generic file classification and lot grouping out of DLS-specific
  naming.
- Only rename import paths after tests prove behavior is unchanged.

## Phase 4: Split Metrics By Scientific Domain

Goal: keep pure metric functions reusable and easier to extend.

Preferred long-term shape:

```text
labassistant/metrics/
  particle_size.py
  chromatography.py
  spectroscopy.py
```

Near-term safe move:

- Keep `labassistant/metrics.py` as the public compatibility module.
- First move DLS distribution metrics into a non-conflicting module such as
  `labassistant/particle_size_metrics.py`, then import and re-export them from
  `metrics.py`.
- Convert `metrics.py` into a `metrics/` package only when the extra package
  churn is justified, preserving compatibility through `metrics/__init__.py`.
- Add tests around compatibility imports before and after each move.

## Phase 5: Build The General Reasoning Layer

Goal: move scientific interpretation out of instrument-specific modules and into
experiment-level reasoning.

Preferred long-term shape:

```text
labassistant/reasoning/
  trend_analysis.py
  anomaly_detection.py
  reproducibility.py
  quality_assessment.py
  experiment_brief.py
  hypothesis_engine.py
```

Near-term safe move:

- Move or facade `labassistant/trend_analysis.py` into
  `reasoning/trend_analysis.py`.
- Extract reusable reproducibility and outlier logic from trend analysis.
- Rename new brief-building work to `experiment_brief`.
- Make reasoning APIs accept experiments first and observations as the primary
  reasoning input, with measurements available as nested evidence.
- Keep DLS-specific aggregation interpretation in particle-size quality until a
  general observation/evidence model exists.

## Phase 6: Add A Memory Layer

Goal: compare new experiments against prior scientific context across
instruments and over time.

Capabilities:

- Similar experiment search.
- Pattern recurrence detection.
- Long-term batch/formulation trends.
- Links between early analytical signals and later stability outcomes.
- Correlation discovery across variables and outcomes.

Near-term safe move:

- Keep local JSONL history.
- Add stable experiment IDs and provenance.
- Support append-only rehydration: loading a saved DLS experiment restores
  editable circulation-time and filtration values, while saving creates a new
  version with lineage provenance.
- Avoid migrating to SQLite until query needs justify it.
- Define historical comparison interfaces before changing storage.

## Phase 7: Experiment Reports

Goal: generate reports that describe experiments, not datasets.

Capabilities:

- Experiment question and context.
- Measurements and instruments used as supporting evidence.
- Cross-instrument observations.
- Trustworthiness and reproducibility assessment.
- Historical comparison.
- Interpretation and recommended next action.

Near-term safe move:

- Keep current dashboard summaries working.
- Add report data structures that consume an `Experiment`, not raw uploaded
  files or isolated dataframes.
- Let Zetasizer/DLS report sections be one technique-specific subsection inside
  the broader experiment report.

## Phase 8: Add The Next Instrument Adapter

Goal: prove the platform architecture with a second technique.

Recommended next candidate: HPLC or SEC, because both exercise new concepts:
chromatographic peaks, retention time, integration quality, and impurity or
fragment profiles.

Do this only after the ingestion/reasoning boundary is clear enough that the new
adapter does not duplicate DLS-specific assumptions.

## Phase 8a: Chromatography Mass-Balance Design

Goal: model chromatography and mass-balance reasoning before building a parser.

Current safe move:

- Add `ChromatographyPeak`, `ChromatographyMeasurement`, and
  `MassBalanceAssessment` models.
- Generate normalized observations from populated chromatography models.
- Add hypotheses for incomplete recovery, degradation into detected or
  non-detected species, co-elution, integration error, matrix effect,
  response-factor mismatch, adsorption/sample prep loss, insoluble
  aggregate/precipitate formation, and method instability.
- Cross-link DLS aggregation observations with chromatography recovery or total
  area loss to suggest missing mass may be insoluble or aggregated.
- Do not implement full HPLC parsing until representative exports are available.

See `docs/CHROMATOGRAPHY_MASS_BALANCE.md`.

## Safe Incremental Refactor Proposal

The safest next refactor is a compatibility-first package split:

1. Add lightweight `Workspace`, `Project`, `Experiment`, and `Observation`
   dataclasses to `labassistant/models.py`, keeping the existing `Measurement`
   API intact.
2. Add an experiment assembly helper that wraps the current imported
   `Measurement` list in a default workspace/project/experiment envelope.
3. Add observation extraction helpers that convert current DLS warnings,
   derived metrics, aggregation assessments, and reproducibility analyses into
   normalized observations.
4. Add `labassistant/ingestion/zetasizer.py` that wraps the existing DLS importer
   and returns measurements ready for experiment assembly.
5. Add `labassistant/reasoning/experiment_brief.py` that wraps the current
   decision brief functions from `interpretation.py`.
6. Add `labassistant/reasoning/reproducibility.py` and move only pure
   percent-RSD/outlier helpers from `trend_analysis.py` behind compatibility
   imports.
7. Add `labassistant/particle_size_metrics.py` behind the existing
   `labassistant/metrics.py` compatibility module; later convert to a
   `metrics/particle_size.py` package layout when callers are ready.
8. Update tests to assert the current DLS dashboard and importer behavior are
   unchanged.

This moves the codebase toward instrument-agnostic scientific reasoning while
preserving the current Zetasizer workflow and avoiding a large rewrite.

## Phase 8 (Delivered): First Chromatography Language

LabAssistant learned its first chromatography language, the Agilent OpenLab
`.olax` archive, and grew a reasoning layer.

- `Experiment` aggregation object added to `models.py` (instrument-agnostic
  container for measurements + observations).
- `build_experiment_from_olax` adapter: opens the archive, enumerates
  injections, classifies detector/method/audit/calibration files, builds
  `ChromatographyMeasurement` objects, and attaches an Observation stream.
- Part 4 Observation vocabulary with a `data_completeness` category convention
  for gaps (missing peak table, unknown detector, processing method missing).
- `investigator.py` (Scientific Investigator): deterministic reasoning over
  Observations answering what happened / complete / missing / interpretable /
  confidence improvers.
- Documentation: `docs/OPENLAB_ARCHITECTURE.md`.

See `docs/OPENLAB_ARCHITECTURE.md` for the full design and the list of unknowns
still pending validation against the real archives.

## Phase 9 (Proposed): From Located To Decoded

Phase 8 *locates* chromatographic evidence; Phase 9 *decodes and interprets* it.

1. **Validate against real archives.** Confirm the OpenLab CDS folder hierarchy,
   detector container formats, and results/ACAML schema using the two provided
   `.olax` files; update the classifier tables and the UNKNOWN sections in the
   architecture doc.
2. **Decode detector signals.** Parse `.CH`/`.UV`/MS containers into
   time/intensity arrays; render chromatograms in the dashboard.
3. **Parse peak tables into `ChromatographyPeak`.** Wire integrated peaks and
   quantitation into the existing `MassBalanceAssessment` engine.
4. **Chromatography Investigator rules.** Extend the Investigator with
   technique-aware checks: system suitability (blanks/standards present),
   calibration validity, replicate %RSD, mass-balance conservation.
5. **Cross-technique reasoning.** Link HPLC "missing mass" to DLS aggregation
   observations (the hypothesis link already exists) to move toward true
   mass-balance investigation.
6. **Second instrument.** Add one more importer (SEC or UV-Vis) against the same
   Experiment/Observation contract to prove the architecture generalizes.
7. **Audit trail + provenance surfacing.** Parse the audit trail and expose
   data integrity / signature status as Observations.
