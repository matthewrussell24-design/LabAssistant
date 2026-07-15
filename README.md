# LabAssistant

LabAssistant is a standalone Experiment Intelligence application that
transforms laboratory data into scientific insight across the lifecycle of a
scientific experiment.

The current working surface is a Streamlit app, but LabAssistant should not be
treated as merely a Streamlit analysis tool. Streamlit is the first human-facing
shell around a reusable application core. The product direction is:

- Human users first: scientists should be able to import, review, compare, and
  report experiments in a dedicated LabAssistant application.
- Application core second: ingestion, domain models, reasoning, memory, and
  reporting should live outside UI code.
- Agent-ready later: future agents should be able to use stable experiment and
  observation APIs, but agent infrastructure should not be overbuilt before the
  human workflow and domain boundaries are solid.

The current working product supports a Zetasizer/DLS workflow, but that workflow
is the first use case rather than the final product. The long-term application
goal is:

```text
Define or upload an experiment -> LabAssistant gathers observations from every
available measurement, explains what happened, whether the result is
trustworthy, why it matters, and what to do next.
```

Every experiment should answer four questions:

1. What happened?
2. Is it real/trustworthy?
3. Why does it matter?
4. What should the scientist do next?

The intelligence layer is the product. Instruments are plugins. Experiments are
first-class objects. Measurements are building blocks.

## Standalone Application Direction

LabAssistant should evolve into a standalone app with a clear boundary between
the product shell and the scientific core:

- `app.py` is the current Streamlit shell for human users.
- `labassistant/` is the reusable application and scientific core.
- `labassistant.application` exposes the first tiny app-level manifest and
  read-only experiment snapshot contract.
- Future UI shells, report exporters, local services, or agent clients should
  consume the same core rather than scrape Streamlit state.

The planned agent-access layer is intentionally modest right now. It should
start with stable, read-only access to experiments, observations, summaries,
provenance, and reports. It should not yet include autonomous lab operation,
instrument control, remote API hosting, or speculative LLM orchestration.

## Current Supported Use Case

LabAssistant currently focuses on DLS/Zetasizer uploads from Malvern Orchestra
exports:

- Upload multiple CSV or Excel files at once.
- Preview automatically grouped lots before import.
- Merge summary/statistics exports, intensity size distributions, and
  correlogram files into one `Measurement` per lot.
- Calculate LabAssistant-derived scientific metrics.
- Explore forward-angle size/PDI relationships against explicitly entered
  experiment variables.
- Use dual-angle Aggregation Index as supporting multi-detector evidence.
- Summarize quality, reproducibility, drift, and historical similarity.
- Start the dashboard with an Experiment Brief instead of raw charts.

The Zetasizer workflow should remain stable while the backend moves toward
experiment-first ingestion, metrics, reasoning, memory, and reporting.

## Run Locally

Use `scripts/run` for the existing Streamlit application.

On macOS, use `scripts/run-desktop` for the native desktop prototype. Select
the summary, intensity-distribution, and correlogram files that make up an
existing supported DLS dataset. The native AppKit/WebKit runtime is installed
through the pinned PyObjC packages in the native desktop lock under
`requirements/locks/` (the full `requirements.txt` setup includes it).

To make the stable local reads available only for that desktop session, opt in
explicitly:

```bash
scripts/run-desktop --share-local-reads
```

Normal desktop startup remains listener-free. The opted-in broker stops with
the app and removes only its owned socket; a compatible separately started
broker remains externally owned.

### Local macOS Bundle Qualification

On an arm64 Mac, build the explicitly non-release standalone qualification app:

```bash
scripts/build-macos-qualification
scripts/inspect-macos-qualification
scripts/smoke-macos-qualification
```

The artifact is `/tmp/LabAssistantQualification.app`, carries the development
identity `dev.labassistant.local-qualification`, is ad-hoc signed, and is labeled
“Local Only.” It is intentionally outside the repository because it is a
temporary host-qualification artifact, not a distributable release. The audit
requires every Mach-O to be arm64 and rejects Streamlit, Plotly, pytest, linked
development paths, and an invalid signature. The smoke exercises packaged
DLS/XLSX, chromatography CSV, synthetic OpenLab `.olax`, JSONL history, SQLite
memory, paths with spaces, and default-off IPC.

This bundle uses a checksum-pinned controlled CPython runtime and declares a
candidate macOS 14.0 binary floor from its complete native closure. It is not
Developer ID signed, hardened/notarized, sandboxed, universal2, or yet validated
on clean macOS 14/current machines, so the declaration is not a support claim.

The desktop app opens into a research workspace with reusable experiment,
metric, analysis, and session-history cards. Streamlit remains available for
the broader compatibility workflow.

The stable seven-read `1.0` contract is also available through an explicit
foreground, owner-only local broker on macOS:

```bash
scripts/run-read-broker
scripts/read-api describe_platform
scripts/read-api list_experiments --parameters '{"limit": 5}'
```

The broker uses Unix-domain IPC, verifies the connecting OS user, and never
opens a network port. Stop it with `Ctrl-C`. Its first trust boundary is the
current local OS user; it is not remote authentication and does not expose
writes.

Python clients can use immutable typed results without parsing transport or
application envelopes:

```python
from labassistant import LocalReadClient

client = LocalReadClient()
experiments = client.list_experiments(limit=5)
for item in experiments.data.items:
    print(item.record_id, item.label)
```

The client does not start the broker. Connection, transport, protocol, and
stable application failures use distinct `LocalRead*Error` types.

## Product Direction

LabAssistant should eventually support multiple analytical techniques:

- DLS / Zetasizer
- HPLC
- SEC
- UV-Vis
- ELISA
- DSC
- Rheology
- Stability studies
- Other laboratory instrument outputs

Instrument-specific logic belongs in ingestion/parsing modules. Scientific
reasoning should be general and reusable across instruments, conditions,
batches, formulations, and time.

Reports should describe experiments, not datasets. Instrument exports and
measurements are supporting evidence inside an experiment-level narrative.
LabAssistant should analyze experimentally relevant relationships directly
rather than force every interpretation through a predefined literature metric.
Experiment variables must be explicitly entered or imported from source data;
they should not be inferred from lot names, file order, or other incidental
metadata.

The current DLS concepts should evolve into broader platform concepts:

| Current DLS feature | Platform concept |
| --- | --- |
| Aggregation detection | Particle quality assessment |
| Percent RSD | Reproducibility analysis |
| Drift detection | Trend analysis |
| Outlier detection | Quality control |
| Dual-angle comparison | Multi-detector comparison |
| Decision Brief | Experiment Brief |
| Zetasizer importer | One supported ingestion adapter |

## Current DLS Capabilities

### Forward-Scatter Trend Explorer

The current DLS investigation is relationship-first: total circulation time is
entered explicitly for each imported sample, keyed by the current sample name,
and LabAssistant extracts the forward-angle summary from
`Measurement.angle_summaries`. It then analyzes:

- circulation time vs forward-angle mean Z-average
- circulation time vs forward-angle mean PDI

When at least three valid samples with distinct circulation times are available,
LabAssistant reports Pearson correlation with restrained relationship language
such as weak, moderate, or strong. The statistic is presented as correlation,
not causation or proof. If there are too few observations or no circulation-time
variation, the app says so instead of producing a misleading statistic.

The planned orthogonal follow-up is to run the same samples on a filtration
device and test the working hypothesis chain:

```text
circulation time -> forward-scatter size/PDI -> filtration difficulty
```

Filtration may strengthen or weaken the relationship hypothesis because it is a
separate measurement of sample behavior rather than another DLS-derived metric.

### Filtration Follow-Up Workflow

LabAssistant supports a first generic filtration follow-up workflow for the
same samples reviewed by DLS. Filtration evidence can be entered manually or
imported from a simple CSV; it is stored on each DLS `Measurement` as orthogonal
follow-up provenance.

The filtration difficulty score is an ordinal, operator-assessed rubric, not a
continuous physical measurement:

| Score | Meaning |
| --- | --- |
| 1 | Filters easily; no meaningful resistance. |
| 2 | Slight resistance or slower than baseline. |
| 3 | Moderate filtration difficulty. |
| 4 | High resistance, substantial slowdown, or strong clogging tendency. |
| 5 | Severe filtration difficulty; near-failure or inability to complete normally. |

Because difficulty is ordinal, LabAssistant uses Spearman rank correlation for
relationships involving filtration difficulty, such as difficulty vs
forward-angle Z-average, difficulty vs forward-angle PDI, and difficulty vs
circulation time. Pearson correlation remains appropriate for continuous
relationships such as circulation time vs forward-angle Z-average/PDI. All
relationship language remains restrained and correlation-only.

Pressure values preserve the originally entered value and unit while also
normalizing supported units to kPa. Supported pressure units are `Pa`, `kPa`,
`bar`, and `psi`; unsupported or missing units are reported rather than assumed.

The generic filtration CSV importer supports conservative column matching for:

```text
sample name, difficulty score, filtration time, filtration time unit,
pressure, pressure unit, filter type, clogging observed, notes
```

Rows with invalid sample names or non-rubric difficulty scores are skipped with
row-level warnings. Extra columns are ignored and reported. This is intentionally
not a proprietary device parser.

Saved DLS experiments can be loaded back into the current editable workspace.
History remains append-only: loading restores circulation-time and filtration
values for editing, and saving creates a new saved version with lineage
provenance rather than silently mutating the prior record.

`FiltrationMeasurement` also has optional generic trace support for future
device outputs: time values, normalized pressure-over-time, optional flow rate,
and source/provenance metadata. No advanced curve analytics are implemented yet.

### Dual-Angle Comparison as Supporting Evidence

LabAssistant implements Malvern Panalytical's dual-angle protein-aggregation
method (application notes AN101104 and AN140527). Forward scatter (~12.8 deg) is
more sensitive to a small number of large species than backscatter (~173 deg), so
a gap between the two angles can be an early aggregation signal:

```text
Aggregation Index = Z-average(forward) / Z-average(backscatter) - 1
```

The index is treated as supporting multi-detector evidence, not the primary
trend metric for the current larger-particle system and not proof of
aggregation. The Malvern application note was designed for small-protein
aggregation around 1-10 nm, so the published reference thresholds may not
transfer directly. The assessment still checks index magnitude,
forward/backscatter Z-average separation, intensity distribution evidence,
correlogram confidence, and replicate consistency, but it does not gate or
override the direct forward-scatter relationship analysis.

### Multi-File Import Workflow

The current importer lives in:

- `labassistant/importers/file_classifier.py`
- `labassistant/importers/lot_grouper.py`
- `labassistant/importers/measurement_importer.py`
- `labassistant/importers/dls.py`

Streamlit uses multi-file upload. After files are selected, the app previews:

```text
Lot | Summary file | Intensity file | Correlogram file | Status
```

For each detected lot, `measurement_importer.py` creates one merged
`Measurement`:

- Summary/statistics data supplies Z-average, PDI, count rate, per-angle
  summaries, and metadata.
- Intensity distribution data supplies curves, replicate distributions, peaks,
  D10/D50/D90, tail area, and distribution width.
- Correlogram data supplies replicate correlation pairs and signal/noise
  quality.

Do not generate graph or derived distribution metrics from summary-only data
when distribution files are available.

### LabAssistant-Derived Metrics

`labassistant/metrics.py` computes pure scientific metrics from distributions:

- `count_peaks`
- `calculate_peak_width`
- `calculate_peak_symmetry`
- `calculate_log_skewness`
- `assess_aggregation_risk`
- `calculate_quality_score`

`labassistant/trend_analysis.py` holds reusable series analysis for
reproducibility, drift, change points, and outliers. This module is one of the
first signs of the future instrument-agnostic reasoning layer.

## Future Memory Layer

LabAssistant should eventually remember prior experiments and compare new data
against historical results:

- Have we seen this pattern before?
- Which experiments are most similar?
- Did similar patterns later fail stability testing?
- Are there long-term trends across batches or formulations?
- Which variables correlate with better outcomes?

The current local history implementation is intentionally small:

- Store uploaded experiments with `history.save_experiment`.
- Compare new uploads to previous runs with `history.compare_to_history`.
- Track Z-average and PDI trends with `history.trend_table`.
- Search saved experiments with `history.find_similar_samples`.

Mutable runtime data no longer depends on the launch directory. On macOS,
history and scientific memory default beneath
`~/Library/Application Support/LabAssistant/`; the optional local-read socket
uses `~/Library/Caches/LabAssistant/runtime/`. `LABASSISTANT_DATA_HOME` and
`LABASSISTANT_CACHE_HOME` provide explicit overrides.

Existing repository-relative data is never discovered or moved automatically.
Import an explicitly reviewed legacy directory with a copy-only migration:

```bash
scripts/migrate-runtime-data --from /absolute/path/to/legacy-root
```

The command accepts only the known history and memory files, rejects links and
destination conflicts, and leaves the originals unchanged.

The long-term memory layer should compare observations across instruments and
over time, not only compare one uploaded dataset to another.

## Documentation Map

The repository development workflow and complete documentation index live in
[`docs/README.md`](docs/README.md).

For the fastest project handoff, read
[`docs/status/current-state.md`](docs/status/current-state.md). LabAssistant uses
a five-minute rule: each important document should make its purpose clear within
five minutes.

Start here when changing product or architecture direction:

1. `docs/status/current-state.md` — Where are we?
2. `docs/ROADMAP.md` — Where are we going?
3. `docs/ARCHITECTURE.md` — Why is it built this way?
4. `AGENTS.md` — How should an AI work here?
5. `docs/prompts/*.md` — What should be implemented next?

Product principles live in `docs/VISION.md`; standalone and agent-access
boundaries live in `docs/STANDALONE_APP.md`. `docs/AGENT_HANDOFF.md` orients a
new agent to the current direction and next best move as a companion to the
status page, and `LabAssistant_Vision_and_Roadmap.md` remains a legacy
compatibility pointer.

The status page is the operating system for contributor coordination:

```text
README
  -> current-state.md
       -> Roadmap
       -> Architecture and decisions
       -> Implementation prompts
            -> Human contributors and Codex
```

Other documents provide durable detail; `current-state.md` tells contributors
which detail matters now and identifies the safest next action.

## Local Setup

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

That compatibility entry point installs the hashed Python 3.12 macOS arm64
development lock. Narrower hashed locks are available for native desktop,
Streamlit, and desktop-build environments under `requirements/locks/`; see
[`requirements/README.md`](requirements/README.md).

Run the app:

```bash
scripts/run
```

Or run it through the activated virtual environment:

```bash
python -m streamlit run app.py
```

Run tests:

```bash
scripts/test -q
```

## Project Structure

Current structure:

```text
LabAssistant/
  app.py
  requirements.txt
  requirements/
  README.md
  LabAssistant_Vision_and_Roadmap.md
  labassistant/
    application.py
    aggregation.py
    history.py
    interpretation.py
    measurements.py
    metrics.py
    models.py
    quality.py
    trend_analysis.py
    view_models.py
    importers/
      dls.py
      file_classifier.py
      lot_grouper.py
      measurement_importer.py
  tests/
  docs/
    AGENT_HANDOFF.md
    ARCHITECTURE.md
    ROADMAP.md
    STANDALONE_APP.md
    VISION.md
```

Preferred long-term direction:

```text
labassistant/
  application/
    commands.py
    queries.py
    services.py
  ingestion/
    zetasizer.py
    hplc.py
    sec.py
    uvvis.py
  metrics/
    particle_size.py
    chromatography.py
    spectroscopy.py
  reasoning/
    trend_analysis.py
    anomaly_detection.py
    reproducibility.py
    quality_assessment.py
    experiment_brief.py
    hypothesis_engine.py
  reports/
    export.py
  agent_access/
    readonly_api.py
    schemas.py
  models/
    experiment.py
    measurement.py
```

Do not force that full split in one rewrite. Move one stable backend boundary at
a time and keep the current Zetasizer workflow covered by tests.
