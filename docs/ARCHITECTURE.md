# LabAssistant Architecture Notes

This document captures the intended architecture so future agents can make
changes that fit the broader product direction instead of only patching the
current Streamlit app.

## Strategic Frame

LabAssistant is a standalone Experiment Intelligence application that
transforms laboratory data into scientific insight across the lifecycle of a
scientific experiment. The current Streamlit app is the first human-facing shell
around the core. The current Zetasizer/DLS workflow is the first supported use
case, not the final product.

Architecture principle:

```text
UI shells call application services.
Application services call the scientific core.
Instrument-specific code lives in ingestion/parsing modules.
Scientific reasoning is general and reusable across instruments, conditions,
time points, batches, and experiment histories.
Future agent clients use stable read-only app contracts before write commands.
```

The intelligence layer is the product. Instruments are plugins. Experiments are
first-class objects. Measurements are building blocks.

## Current State

LabAssistant currently has a Streamlit shell backed by a small `labassistant`
package.

The backend package already does several useful jobs:

- Reads CSV, XLS, and XLSX uploads.
- Classifies DLS export files as summary, intensity distribution, correlogram,
  or unknown.
- Groups related lot files before import.
- Parses Zetasizer/Orchestra DLS exports through `labassistant/importers/dls.py`.
- Converts importer results into `Measurement` objects through
  `labassistant/measurements.py`.
- Calculates particle-size metrics through `labassistant/metrics.py`.
- Applies quality thresholds through `labassistant/quality.py`.
- Detects dual-angle aggregation signals through `labassistant/aggregation.py`.
- Builds decision-oriented summaries through `labassistant/interpretation.py`.
- Analyzes reproducibility, drift, change points, and outliers through
  `labassistant/trend_analysis.py`.
- Stores local experiment history through `labassistant/history.py`.

This is a strong foundation, but naming and module boundaries still reflect the
first DLS use case more than the long-term platform.

`labassistant.application` now provides the app-level boundary used by two
human shells:

- `app_manifest()` describes the standalone app direction.
- `agent_access_policy()` documents current planned agent access and non-goals.
- `build_experiment_snapshot(experiment)` returns a read-only summary suitable
  for UI navigation, reports, and future agent context selection.
- `analyze_dls_dataset(paths)` accepts existing local DLS files and returns a
  typed, read-only experiment/result summary after running the shared importer,
  metrics, and observation workflow.

`app.py` remains the compatible Streamlit shell. `labassistant.desktop` is a
minimal PySide6 shell that owns only native widgets, file selection, error
display, and formatting. It imports no Streamlit code and contains no
scientific logic. Both shells depend inward on application contracts.

## Preferred Long-Term Shape

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
    workspace.py
    project.py
    experiment.py
    observation.py
    measurement.py
```

Do not force this full split in one large rewrite. Extract one stable boundary
at a time, with tests around behavior before and after the move.

The current `labassistant/application.py` file can stay as a compatibility
facade until there is enough application-service code to justify the
`application/` package split.

## Standalone App Boundary

The app boundary should be explicit:

```text
Streamlit shell now, future app shell later
  -> application queries and commands
  -> Experiment / Observation / Measurement core
  -> ingestion, reasoning, memory, reports
```

`app.py` may own layout, widgets, session state, and local UI affordances. It
should not be the only place that knows how to assemble experiments, query
history, retrieve memory, or produce report-ready summaries.

Application queries should be read-only and easy to test. Application commands
should be explicit, validated, and provenance-preserving.

The future agent-access layer should sit on top of application queries first.
It should return versioned snapshots, context packets, observations, and report
summaries before it ever exposes write commands. Any future write path should
reuse the same command validation used by the human app.

## Domain Model Direction

The target domain hierarchy is:

```text
Workspace
  Project
    Experiment
      Observation
        Measurement
```

`Workspace` is the top-level environment for a scientist, team, or laboratory.
It owns projects, preferences, access, and long-term memory.

`Project` is a long-running research effort. It owns many experiments and gives
them shared context such as program goals, formulation space, methods, batches,
or study design.

`Experiment` is the top-level scientific work unit. It should represent the
question, hypothesis or purpose, method, formulation, batch, condition, time
point, replicate set, observations, conclusions, recommendations, and report.

`Observation` is a normalized scientific finding. It can originate from an
instrument, statistical analysis, AI reasoning, or manual notes. Examples:
forward scatter increased, high percent RSD, stable baseline, peak broadening,
or sample appeared cloudy.

`Measurement` should represent raw analytical data from one instrument,
independent of where the data came from. Measurements are evidence blocks that
produce observations; the reasoning engine should compare the observations
across instruments and over time.

Preferred future relationship:

```text
Experiment
  metadata
  scientific_question
  conditions
  measurements[]
  observations[]
  reasoning_results
  historical_context
  recommended_next_actions
  reports[]
```

Current architecture bridge:

```text
Current Measurement
  -> initial Measurement evidence block
  -> generated Observation records
  -> Experiment envelope
  -> future Project and Workspace containers
```

Current `Measurement` fields map naturally to the platform:

- `metadata`: sample name, date/time, instrument, operator, temperature, method,
  source files, and instrument-specific raw fields.
- `summary_metrics`: normalized scalar measurements.
- `distributions`: curves or paired x/y series when present.
- `correlogram`: DLS-specific signal data for now; future models may generalize
  this as detector or raw signal traces.
- `derived_metrics`: LabAssistant-computed metrics.
- `angle_summaries`: DLS dual-angle detector summaries; future equivalent is a
  multi-detector comparison model.
- `flags`: quality, parsing, reproducibility, and review signals.
- `interpretation`: experiment brief or AI-ready summary.
- `provenance`: source file, sheet, table, column, and parser confidence details.

For DLS, lot-level distribution-derived metrics have one canonical intensity
evidence rule: prefer the averaged backscatter curve, otherwise use the sole
available angle average, then the average of all valid intensity replicates,
and finally the legacy intensity curve. Forward-angle curves remain separate
aggregation-sensitive evidence. Volume and number distributions are not valid
substitutes for this intensity contract, and provenance records the selected
source.

Delimited DLS ingestion accepts comma, semicolon, tab, and pipe separators and
period or comma decimal marks. Single-angle summaries remain explicit
per-angle evidence. Volume-only and number-only curves may be parsed as source
data, but they are rejected as intensity-file roles and do not produce
intensity-derived peaks, percentiles, shape metrics, or aggregation risk.

The existing `Measurement` model should fit under the new hierarchy as the raw
analytical evidence layer. Its derived metrics and flags should be converted
into `Observation` objects for reasoning. For example:

| Existing source | Observation |
| --- | --- |
| `angle_summaries` + aggregation index | Forward scatter increased |
| replicate statistics | High percent RSD |
| correlogram quality | Stable or noisy baseline |
| distribution metrics | Peak broadening or large-particle tail |
| manual notes | Sample appeared cloudy |

The measurement object should not know whether the data came from a CSV export,
Excel workbook, pasted graph data, or a future proprietary format. The
experiment object should know why the measurements belong together. The
observation object should give the reasoning engine a stable scientific language
above instrument-specific details.

## Ingestion Direction

Ingestion modules should produce structured intermediate data that can merge
into normalized measurements, generate observations, and then assemble
first-class experiments.

Instrument adapters may be opinionated:

- Zetasizer/DLS adapters can know about Orchestra exports, scattering angles,
  PDI, correlograms, and intensity distributions.
- HPLC/SEC adapters can know about retention time, peak area, integration, and
  chromatograms.
- UV-Vis adapters can know about wavelength, absorbance, baselines, and
  calibration curves.

Shared ingestion helpers should stay generic:

- file classification
- batch grouping
- experiment assembly
- observation extraction
- provenance capture
- table extraction
- parser confidence
- unit normalization

## Metrics Direction

Metrics should be pure, deterministic, unit-aware, and covered by focused tests.

Scientific-domain metric modules should own calculations:

- `particle_size.py`: DLS/particle distribution metrics, aggregation screening
  features, D10/D50/D90, tails, width, skew, peak count.
- `chromatography.py`: retention time, peak area, resolution, tailing factor,
  impurity percentage, integration quality.
- `spectroscopy.py`: absorbance features, baseline drift, peak wavelength,
  calibration fit, concentration estimates.

For compatibility, existing imports from `labassistant/metrics.py` should keep
working until callers are migrated. Because `metrics.py` currently occupies the
`labassistant.metrics` import name, the first low-risk extraction can use a
temporary non-conflicting module such as `particle_size_metrics.py`; convert to a
`metrics/` package later with `metrics/__init__.py` re-exporting the old public
API.

## Chromatography And Mass Balance Direction

Chromatography should become the first major non-DLS analytical domain. The
initial goal is mass-balance investigation, not full HPLC support.

Minimal future-facing models now exist for:

- `ChromatographyPeak`
- `ChromatographyMeasurement`
- `MassBalanceAssessment`

These models should generate `Observation` objects such as parent peak
decreased, known impurity increased, unknown peak appeared, total area
decreased, retention time shifted, peak broadened, peak tailing increased,
baseline changed, integration boundary changed, replicate percent RSD elevated,
and recovery control failed.

The cross-instrument reasoning target is important: when DLS observations
suggest aggregation or large-particle formation and chromatography observations
suggest reduced recovery or unexplained mass loss, LabAssistant should raise the
hypothesis that missing mass may be associated with insoluble or aggregated
material rather than chromatographically visible degradation.

See `docs/CHROMATOGRAPHY_MASS_BALANCE.md` for the full module proposal.

## Reasoning Direction

Reasoning modules answer the four experiment questions:

1. What happened?
2. Is the evidence trustworthy?
3. Why might it have happened?
4. What should be investigated next?

General reasoning capabilities:

- `trend_analysis.py`: drift, slope, change points, historical trends.
- `anomaly_detection.py`: unexpected values, outliers, pattern breaks.
- `reproducibility.py`: replicate agreement, percent RSD, run consistency.
- `quality_assessment.py`: trustworthiness and evidence strength.
- `experiment_brief.py`: concise scientific conclusion and next action.
- `hypothesis_engine.py`: possible explanations and follow-up experiments.

The reasoning engine should operate primarily on observations, comparing them
across instruments and over time. Raw measurements remain available for
traceability and drill-down, but they should not be the main reasoning surface.
Instrument-specific reasoning can exist, but it should emit general observation
and evidence objects instead of becoming the top-level product frame.

## Reporting Direction

Reports should be generated from normalized experiments and reasoning outputs,
not directly from Streamlit state, uploaded files, or individual datasets.
Reports describe experiments, not datasets.

Future report exports may include:

- scientist-facing experiment briefs
- batch comparison summaries
- stability risk summaries
- method validation summaries
- PDF, DOCX, or slide exports

## UI Direction

The human app should stay decision-oriented.

Show first:

- Experiment Brief.
- Experiment context and purpose.
- Samples needing review.
- Trustworthiness and evidence strength.
- Primary scientific comparison.
- Recommended next action.

Hide secondary diagnostics inside expandable sections.

`app.py` should eventually become a thin Streamlit entry point that calls
application services and renders returned view models.

## Agent-Access Direction

Agents are future clients of LabAssistant, not the primary product in the near
term.

Near-term contract:

- Stable app manifest and access policy.
- Read-only `ExperimentSnapshot` objects.
- Compact context packets from the `ContextRetriever`.
- Report-ready summaries generated from experiments and observations.

Non-goals until the human app and service layer are stable:

- autonomous lab operation
- instrument control
- remote API hosting
- broad LLM orchestration
- write actions that bypass human review

## Migration Guardrails

- Preserve the working Zetasizer workflow.
- Preserve the human app workflow while extracting app services.
- Promote `Experiment` before introducing new instrument-specific surfaces.
- Treat file import as the first step of experiment assembly, not the product
  center.
- Treat Streamlit as the current shell, not the product architecture.
- Keep old import paths working while introducing new package boundaries.
- Add compatibility facades before renaming modules.
- Add tests before changing parser heuristics.
- Move pure functions first; move stateful UI code last.
- Prefer dataclasses or typed models before introducing persistence changes.
- Keep product decisions in docs when code alone would not explain the why.
