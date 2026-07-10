# LabAssistant Vision

LabAssistant is a standalone Experiment Intelligence application that
transforms laboratory data into scientific insight across the lifecycle of a
scientific experiment.

It should not be framed primarily as a Zetasizer/DLS dashboard or a Streamlit
analysis tool. The current Streamlit app is the first human-facing shell, and
the current Zetasizer/DLS workflow is the first supported use case, not the
final product.

The core product goal is:

```text
Define or upload an experiment -> LabAssistant gathers observations from every
available measurement, explains what happened, whether the result is
trustworthy, why it matters, and what to do next.
```

## Product Thesis

The intelligence layer is the product. Instruments are plugins.
Experiments are first-class objects. Measurements are building blocks.
Human scientists are the first users. Future agents are planned clients of the
same stable experiment intelligence core, not a separate product bolted onto
the side.

Scientists should not have to manually inspect exported tables, decide which
charts matter, translate noisy metrics into experimental meaning, and then
remember whether this pattern happened before. LabAssistant should do that work
with clear evidence and conservative language.

The platform should reason about the scientific experiment, not merely process
individual files or datasets. A file is an artifact. A measurement is an
observation. An experiment is the unit of scientific meaning.

The standalone app should keep a clean product boundary:

```text
UI shell -> application services -> scientific core -> memory/reporting
```

Agent access should use the same application services later, beginning with
read-only experiment summaries, observations, context packets, and reports.
Autonomous lab operation, instrument control, and speculative agent runtimes are
not part of the near-term product vision.

Every experiment should answer:

1. What happened?
2. Is the evidence trustworthy?
3. Why might it have happened?
4. What should be investigated next?

## Product Hierarchy

LabAssistant should evolve from:

```text
Measurement
Dashboard
```

to:

```text
Workspace
Project
Experiment
Observation
Measurement
```

Definitions:

- `Workspace`: the top-level environment for a scientist, team, or laboratory.
- `Project`: a long-running research effort containing many experiments.
- `Experiment`: a test of a scientific question or hypothesis. It contains
  measurements from one or more analytical techniques and produces observations,
  conclusions, and recommended next investigations.
- `Observation`: a normalized scientific finding. It can originate from an
  instrument, statistical analysis, AI reasoning, or manual notes.
- `Measurement`: raw analytical data from one instrument. DLS is one
  implementation; future measurements include HPLC, SEC, UV-Vis, and others.

The reasoning engine should operate primarily on observations rather than raw
measurements. Measurements provide evidence; observations are the normalized
scientific facts that can be compared across techniques and over time.

## Platform Scope

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

Each technique will have its own ingestion quirks, units, metadata, and
instrument-specific quality checks. Those details should live close to parsing
and normalization. The reasoning layer should stay reusable.

## Experiment Lifecycle

Every architectural decision should support the lifecycle of a scientific
experiment:

1. Plan or identify the scientific question.
2. Ingest observations from one or more instruments.
3. Normalize measurements into comparable evidence.
4. Assess trustworthiness, reproducibility, anomalies, and trends.
5. Compare against prior experiments and related conditions.
6. Explain what happened and why it matters.
7. Recommend the next scientific action.
8. Generate an experiment-level report.

Files, uploads, parsing, and charts are implementation details serving this
lifecycle.

## Architecture Principle

UI-specific code belongs in the current app shell.

Application workflows belong in UI-independent services and query/command
facades.

Instrument-specific code belongs in ingestion/parsing modules.

Scientific reasoning belongs in general modules that can operate on normalized
experiments, observations, measurements, metrics, replicates, time series, and
evidence.

This means:

- A Zetasizer importer can know about Orchestra exports, scattering angles, PDI,
  correlograms, and intensity distributions.
- An HPLC importer can know about chromatograms, retention time, peak area, and
  integration tables.
- A UV-Vis importer can know about wavelength scans, absorbance, baselines, and
  calibration curves.
- Shared reasoning code should compare observations across instruments and over
  time. It should know about trends, reproducibility, anomalies, evidence
  strength, comparability, quality, and experimental conclusions.

## Generalized Concepts

| Current DLS concept | Platform concept |
| --- | --- |
| Aggregation detection | Particle quality assessment |
| Percent RSD | Reproducibility analysis |
| Drift detection | Trend analysis |
| Outlier detection | Quality control |
| Dual-angle comparison | Multi-detector comparison |
| Decision Brief | Experiment Brief |
| Zetasizer importer | One supported ingestion adapter |
| DLS measurement dashboard | Experiment intelligence workspace |

## Memory And Scientific Context

LabAssistant should eventually remember prior experiments and compare new data
against historical results:

- Have we seen this pattern before?
- Which experiments are most similar?
- Did similar patterns later fail stability testing?
- Are there long-term trends across batches or formulations?
- Which variables correlate with better outcomes?

Historical memory is not just persistence. It is scientific context. The system
should get more useful as more experiments pass through it.

## Reports

Reports should describe experiments, not datasets.

An experiment report should summarize the scientific question, conditions,
measurements, evidence, trustworthiness, interpretation, historical comparison,
and recommended next action. Instrument exports and raw datasets are supporting
evidence, not the report's organizing principle.

## Product Behavior

LabAssistant should speak like a careful scientific analyst:

- Make the conclusion easy to find.
- Show the evidence behind the conclusion.
- Separate observation from interpretation.
- Prefer "signal", "suggests", "consistent with", and "repeat/confirm" language
  when evidence is incomplete.
- Recommend next actions that are practical in the lab.
- Avoid overclaiming beyond the available data.

The dashboard should remain decision-oriented: scientists should be able to tell
which samples need attention and why in under 30 seconds.

As the product becomes a standalone application, this decision-oriented behavior
should apply to every shell: Streamlit today, a packaged local app later, and
read-only agent clients after the application service layer is stable.
