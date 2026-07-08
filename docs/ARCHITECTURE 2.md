# LabAssistant Architecture Notes

This document captures the intended architecture so future agents can make
changes that fit the product direction instead of only patching the current
Streamlit file.

## Current State

LabAssistant is currently a Streamlit app backed by a small `labassistant`
package.

The app and backend package already do several jobs:

- Reads CSV, XLS, and XLSX uploads.
- Finds table-like sections in loose instrument exports through
  `labassistant/importers/dls.py`.
- Infers DLS distribution, summary, metadata, and replicate columns.
- Returns structured `ParsedDLSResult` objects from the DLS importer.
- Converts importer results into `Measurement` objects through
  `labassistant/measurements.py`.
- Builds decision briefs and analyst summaries through
  `labassistant/interpretation.py`.
- Calculates early derived metrics such as primary peak, D10/D50/D90,
  tail index, and width ratio through `labassistant/metrics.py`.
- Applies warning thresholds and sample statuses through
  `labassistant/quality.py`.
- Renders a decision-oriented dashboard with summary cards, overlays, and
  expandable diagnostics.

This is useful, but `app.py` still owns Streamlit rendering and some chart/table
helper functions. The next architecture step is to validate the backend importer
against real files before deeper UI refactoring or persistence work.

## Target Shape

The target architecture is:

```text
labassistant/
  models.py        # Measurement and related dataclasses
  importers/       # CSV, Excel, pasted graph data, future formats
  metrics.py       # LabAssistant-derived scientific metrics
  quality.py       # Flags, health scores, warning thresholds
  interpretation.py # Decision brief and AI-ready summaries
  ui/              # Streamlit rendering components
app.py             # Thin Streamlit entry point
tests/             # Parser, model, metric, and workflow tests
docs/              # Roadmap, architecture, handoff notes
```

Do not force this full split in one large rewrite. Extract one stable seam at a
time, with tests around behavior before and after the move.

## Core Domain Model

`Measurement` should represent one experiment independent of where the data
came from.

Expected fields:

- `metadata`: sample name, date/time, instrument, operator, temperature,
  scattering angle, method/SOP, source files.
- `summary_metrics`: Z-average, PDI, peak sizes, peak areas, count rate, and
  replicate statistics.
- `distributions`: intensity, volume, and number distributions when present.
- `correlogram`: correlogram data when present.
- `derived_metrics`: D10/D50/D90, primary peak, peak count, width, symmetry,
  tail area, aggregation risk, skewness, and quality scores.
- `flags`: threshold and parser confidence warnings.
- `interpretation`: decision brief or AI-generated summary.
- `angle_summaries`: per-scattering-angle view for dual-angle runs (forward vs
  back), each with its own count, Z-average, PDI, and representative peak/D50.
  Keep the lot-level fields as the combined view; do not collapse the angles.
- `derived_metrics.aggregation_index`: dual-angle Aggregation Index
  (`Z_forward / Z_backscatter - 1`). The full assessment lives in
  `labassistant/aggregation.py` (`assess_dual_angle_aggregation`), a headline
  scientific feature per Malvern AN101104/AN140527; keep its scoring pure and its
  interpretation copy honest (screening signal, not definitive quantification).

The object should not know whether the data came from a CSV export, Excel
workbook, pasted graph data, or a future proprietary format.

## Importer Direction

Importers should produce structured intermediate data that can merge into a
single `Measurement`.

Near-term importers:

- Summary CSV exports.
- Excel files containing copied graph or summary data.
- Pasted intensity, volume, number, and correlogram tables.

Design importers to preserve provenance. A future agent should be able to tell
which source file, sheet, table, or pasted block produced each field.

## Metric Direction

Derived metrics should become first-class LabAssistant metrics, not just values
embedded in UI code.

Keep metric functions:

- Pure where possible.
- Deterministic.
- Unit-aware by name and documentation.
- Covered by small tests using synthetic distributions.

Current metric logic in `app.py` is a good starting source for extraction:

- `find_local_peaks`
- `calculate_tail_index`
- `calculate_width_ratio`
- `calculate_distribution_percentiles`
- `sample_attention_score`

`labassistant/metrics.py` now also holds the LabAssistant-derived shape metrics:
`count_peaks`, `calculate_peak_width` (log-space FWHM span), `calculate_peak_symmetry`,
`calculate_log_skewness`, `assess_aggregation_risk`, and `calculate_quality_score`.
Keep new metrics here: pure, deterministic, log-aware for size data, and covered
by both synthetic tests (`tests/test_metrics.py`) and real-export regression
tests (`tests/test_real_fixtures.py`, backed by `tests/fixtures/`).

## UI Direction

The dashboard should stay decision-oriented.

Show first:

- Measurement health score.
- Samples needing review.
- Best and worst candidate.
- AI or analyst-style findings.
- Primary distribution overlay.
- Key Z-average/PDI comparisons.

Hide secondary diagnostics inside expandable sections.

`app.py` should eventually become a thin Streamlit entry point that calls the
analysis core and renders returned view models.

## Guardrails

- Preserve working parsing behavior while extracting modules.
- Avoid broad rewrites without representative fixture files.
- Prefer dataclasses or typed models before introducing persistence.
- Add tests before changing parser heuristics.
- Keep product decisions in docs when code alone would not explain the why.
