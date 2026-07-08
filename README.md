# LabAssistant

LabAssistant is an Experiment Intelligence Platform that transforms laboratory
data into scientific insight across the lifecycle of a scientific experiment.

The current working product supports a Zetasizer/DLS workflow, but that workflow
is the first use case rather than the final product. The long-term platform goal
is:

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

## Current Supported Use Case

LabAssistant currently focuses on DLS/Zetasizer uploads from Malvern Orchestra
exports:

- Upload multiple CSV or Excel files at once.
- Preview automatically grouped lots before import.
- Merge summary/statistics exports, intensity size distributions, and
  correlogram files into one `Measurement` per lot.
- Calculate LabAssistant-derived scientific metrics.
- Detect dual-angle aggregation signals.
- Summarize quality, reproducibility, drift, and historical similarity.
- Start the dashboard with an Experiment Brief instead of raw charts.

The Zetasizer workflow should remain stable while the backend moves toward
experiment-first ingestion, metrics, reasoning, memory, and reporting.

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

### Dual-Angle Aggregation Detection

LabAssistant implements Malvern Panalytical's dual-angle protein-aggregation
method (application notes AN101104 and AN140527). Forward scatter (~12.8 deg) is
more sensitive to a small number of large species than backscatter (~173 deg), so
a gap between the two angles can be an early aggregation signal:

```text
Aggregation Index = Z-average(forward) / Z-average(backscatter) - 1
```

The index is treated as a screening signal, not proof of aggregation. The
assessment checks index magnitude, forward/backscatter Z-average separation,
intensity distribution evidence, correlogram confidence, and replicate
consistency before recommending review, repeat, or orthogonal confirmation.

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

The long-term memory layer should compare observations across instruments and
over time, not only compare one uploaded dataset to another.

## Documentation Map

Start here when changing product or architecture direction:

1. `docs/VISION.md` - product vision and platform principles.
2. `docs/ROADMAP.md` - incremental roadmap from DLS workflow to lab
   intelligence platform.
3. `docs/ARCHITECTURE.md` - target module boundaries and current migration
   guidance.
4. `docs/AGENT_HANDOFF.md` - current implementation state and next best moves.
5. `LabAssistant_Vision_and_Roadmap.md` - legacy compatibility pointer to the
   newer split docs.

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
  README.md
  LabAssistant_Vision_and_Roadmap.md
  labassistant/
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
    VISION.md
```

Preferred long-term direction:

```text
labassistant/
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
  models/
    experiment.py
    measurement.py
```

Do not force that full split in one rewrite. Move one stable backend boundary at
a time and keep the current Zetasizer workflow covered by tests.
