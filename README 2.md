# LabAssistant

LabAssistant is a Streamlit application moving from DLS file viewing toward a
laboratory intelligence platform. The core product question is:

> Which sample deserves attention, and why?

The current app focuses on DLS uploads, but the architecture should stay flexible
enough to support HPLC, UV-Vis, SEC, ELISA, microscopy, report generation, and
AI summaries over time.

## Dual-Angle Aggregation Detection (headline feature)

LabAssistant implements Malvern Panalytical's dual-angle protein-aggregation
method (application notes AN101104 and AN140527). Forward scatter (~12.8°) is far
more sensitive to a small number of large species than backscatter (~173°), so a
gap between the two angles is an early aggregation signal:

> Aggregation Index = Z-average(forward) / Z-average(backscatter) − 1

An index near 0 means the angles agree (no aggregate signature); the reference
baseline is ~0.05 for a stable sample rising to ~0.1 at the onset of aggregation.
The feature (`labassistant/aggregation.py`, `assess_dual_angle_aggregation`) uses:

- summary data for the per-angle Z-average values that define the index,
- intensity distribution data to check the forward angle for aggregate peaks or a
  large-particle tail,
- correlogram baseline noise to rate measurement confidence.

The index is never treated as proof of aggregation. Each measurement gets a
**corroboration checklist** (`DualAngleAggregation.checks`) across five evidence
areas — index magnitude, forward vs backscatter Z-average, forward distribution
evidence (large-particle tail, secondary peak, peak shift), correlogram
confidence (baseline noise, decay quality), and replicate consistency across the
two angles — each marked supports / neutral / insufficient. The corroboration
score and measurement confidence drive an **interpretation category**:

- Low signal (index < 0.05)
- Watch (0.05–0.10)
- Elevated (0.10–0.30)
- Strong signal, corroborated (index ≥ 0.30 with confident, independently
  supported evidence)
- Strong signal, repeat recommended (strong index but thin evidence/confidence)

Language stays deliberately non-definitive: "Strong dual-angle aggregation
signal", "Forward-angle large-species enrichment", "Requires corroboration", and
"Recommend review / repeat / orthogonal confirmation".

The dashboard shows this prominently at the top: an Aggregation Index card per
lot with its category and corroboration score, a forward-vs-backscatter
Z-average comparison, an Aggregation Index chart with the watch/elevated lines, a
paired intensity distribution overlay by angle, the corroboration checklist with
supports/neutral/insufficient marks, and the recommendation. Elevated samples are
flagged for review.

## Current Dashboard

The dashboard is being redesigned around fast scientific decision-making:

- Upload multiple DLS CSV or Excel files at once
- Preview automatically grouped lots before importing
- Merge summary/statistics exports, intensity size distributions, and
  correlogram files into one `Measurement` per lot
- Start with a decision brief naming the best sample, sample needing attention,
  flagged count, and next recommended check
- Read a short analyst-style AI summary instead of long generic explanations
- Review compact sample summary cards
- Compare the primary distribution overlay and key Z-average/PDI metrics first
- Expand secondary diagnostics only when needed, including peak plots,
  D10-D90 spread, tail index, signal matrix, scattering-angle coverage, small
  multiples, correlogram signal quality, raw parsed points, metadata, and
  original text

## Multi-File Import Workflow

The current importer is intentionally modular and lives in:

- `labassistant/importers/file_classifier.py`
- `labassistant/importers/lot_grouper.py`
- `labassistant/importers/measurement_importer.py`

Streamlit uses `st.file_uploader(..., accept_multiple_files=True)` rather than
folder upload. After files are selected, the app shows this preview table before
importing:

```text
Lot | Summary file | Intensity file | Correlogram file | Status
```

Supported classifications:

- summary/statistics export
- size distribution by intensity
- correlogram
- unknown

Project-specific lot normalization is important. These all group together:

```text
446-01, Lot 446-01, Lyo 446-01, Lot 1 -> lot_1 / display "Lot 1"
446-02, Lot 446-02, Lyo 446-02, Lot 2 -> lot_2 / display "Lot 2"
446-03, Lot 446-03, Lyo 446-03, Lot 3 -> lot_3 / display "Lot 3"
```

For each detected lot, `measurement_importer.py` creates one merged
`Measurement`:

- summary/statistics data supplies Z-average, PDI, count rate, and metadata
- intensity distribution data supplies graph curves, replicate distributions,
  peaks, D10/D50/D90, tail area, and distribution width
- correlogram data supplies replicate correlation pairs and signal/noise quality

Do not generate graph or derived distribution metrics from summary-only data
when distribution files are available.

## LabAssistant-Derived Metrics

Beyond the instrument's own numbers, `labassistant/metrics.py` computes its own
scientific metrics on the intensity distribution (all pure and unit-documented):

- `count_peaks` — number of resolved size modes.
- `calculate_peak_width` — primary-peak full-width-at-half-maximum, reported as a
  geometric span ratio (upper/lower diameter) because DLS is log-normal.
- `calculate_peak_symmetry` — right/left half-width ratio; > 1 means the peak
  tails toward larger particles (an early aggregation cue).
- `calculate_log_skewness` — intensity-weighted skewness of log10(diameter);
  0 is a clean log-normal, positive means a large-particle tail.
- `assess_aggregation_risk` — Low / Moderate / High from combined evidence (tail
  index, secondary-peak size, PDI, skew, width).
- `calculate_quality_score` — 0-100 heuristic screening score for how clean a
  measurement looks.

`correlogram_noise_score` measures per-replicate baseline scatter (points that
have decayed below 10% of the intercept), averaged across replicates — a real
noise signal, not the spread of the whole decay curve.

## Dual-Angle Measurements

Orchestra exports are dual-angle runs (forward 12.78° + back 174.7°), which
report different apparent sizes at each angle. Blending them hides real
structure, so each `Measurement` also carries `angle_summaries`: one
`AngleSummary` per angle with its count, mean Z-average, mean PDI, max Z, and a
representative primary peak / D50 from the intensity replicates classified to
that angle. Per-angle averaged curves are stored under
`distributions["angle_forward"]` / `["angle_back"]`, and
`view_models.build_angle_table` returns a per-lot/per-angle table for display.

Angle assignment is size-based, not positional: the summary measurement table is
grouped by its reported scattering angle (robust when runs are not cleanly
alternating), and each intensity replicate is matched to the angle whose mean
Z-average is nearest in log space. `count` (measurements) and `replicate_count`
(classified intensity curves) can legitimately differ when the intensity export
contains only a subset of the runs.

These are exposed on `Measurement.derived_metrics` and in the metrics table via
`build_metrics_table`, so the dashboard and interpretation layers can use them.

Validation: the importer and metric engine are covered against trimmed copies of
real Orchestra Zetasizer exports (lot 446-01) in `tests/fixtures/` via
`tests/test_real_fixtures.py`.

Streamlit reruns the script whenever chart controls change. Imported samples are
therefore cached in `st.session_state` using the current uploaded-file batch
signature. Keep the preview/import button as the explicit gate, but keep all
post-import controls, such as reference sample and Delta/Overlay view, reading
from cached imported samples so they do not force the user to import again.

## Product Direction

Near-term improvements should help users answer this in under 30 seconds:

> Are these samples okay, and which one should I care about?

History features let LabAssistant remember previous experiments:

- Store uploaded experiments (`history.save_experiment`, local JSONL)
- Compare new uploads to previous runs (`history.compare_experiments` /
  `compare_to_history`: per-sample Z-average and PDI drift with drift flags,
  shown in the Experiment History panel as "Change vs last saved experiment")
- Track Z-average and PDI over time (`history.trend_table` + trend charts)
- Flag trends and drift (drift thresholds: Z-average ±20%, PDI ±0.10)
- Search past experiments / identify similar samples
  (`history.find_similar_samples`: ranks saved samples by a unit-aware distance —
  log10 ratio for size features, absolute difference for PDI — surfaced in the
  Experiment History panel as "Find similar past runs")

## Project Workflow

Current phase: Phase 3 derived-metric engine and dual-angle handling are done and
validated against real Orchestra exports; Phase 4 dashboard now includes the
per-angle breakdown; Phase 5 history includes storage, trends, and experiment
comparison.

- [x] Build the baseline Streamlit CSV upload app
- [x] Expand the app into a DLS comparison dashboard
- [x] Add a decision brief and shorter analyst-style summary
- [x] Move secondary charts into expandable diagnostic sections
- [x] Smoke test the empty dashboard state
- [x] Validate parser behavior with representative distribution and replicate-summary data
- [x] Build the first `Measurement` data model
- [x] Convert current parsed samples into `Measurement` objects
- [x] Extract derived metric calculations into reusable backend modules
- [x] Extract DLS table parsing and column inference helpers into importers
- [x] Move DLS upload parsing workflow behind a backend importer result
- [x] Move importer-result to `Measurement` conversion into backend modules
- [x] Extract decision brief and interpretation logic into backend modules
- [x] Add multi-file import preview for summary/intensity/correlogram files
- [x] Normalize project lot names so `446-01` and `Lot 1` merge correctly
- [x] Merge grouped files into one `Measurement` per lot
- [x] Use intensity data for distribution-derived metrics and correlogram data
  for signal-quality diagnostics
- [x] Start Phase 4 dashboard redesign with a decision-first layout, sidebar
      import workflow, health strip, and prioritized primary review surface
- [x] Add local Measurement-backed experiment history storage
- [x] Add saved-experiment summary and Z-average/PDI trend views
- [x] Add LabAssistant-derived shape metrics (peak count/width/symmetry,
      skewness, aggregation risk, quality score) with real correlogram baseline noise
- [x] Validate the importer and metrics against real Orchestra Zetasizer exports
      (lots 446-01/02/03) and lock in trimmed fixtures + regression tests
- [x] Capture dual scattering angle (forward 12.78° / back 174.7°) and
      measurement datetime from the Orchestra summary workbook
- [x] Group intensity replicates by angle into per-angle curves and metrics
- [x] Render the per-angle view in the dashboard (Scattering Angle Breakdown:
      per-angle table plus forward/back Z-average and primary-peak charts)
- [x] Expand history into experiment comparison (Z-average/PDI drift vs the last
      saved run, with drift flags)
- [x] Add similar-run search across saved experiments (rank past samples by
      unit-aware distance to a chosen current sample)
- [x] Add dual-angle protein aggregation detection (Aggregation Index) as a
      headline scientific interpretation feature with a prominent dashboard panel
- [ ] Polish parser and dashboard edge cases found during real-file validation

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

```text
LabAssistant/
  app.py                           # Current Streamlit app and analysis logic
  requirements.txt                 # Python dependencies
  README.md                        # Setup notes and project overview
  LabAssistant_Vision_and_Roadmap.md # Product vision and phased roadmap
  labassistant/
    importers/file_classifier.py    # Classifies uploads by export role
    importers/lot_grouper.py         # Normalizes lot keys and builds preview rows
    importers/measurement_importer.py # Multi-file preview and Measurement merge
    importers/dls.py                # DLS table parsing and column inference
    aggregation.py                  # Dual-angle protein aggregation detection
    history.py                      # Local experiment history persistence
    interpretation.py               # Decision brief and analyst summaries
    measurements.py                 # Importer result to Measurement conversion
    metrics.py                      # Pure derived metric calculations
    models.py                      # Measurement dataclasses
    quality.py                     # Warning thresholds and statuses
    view_models.py                  # Dashboard-compatible sample view models
  tests/                           # Model and adapter tests
  docs/
    AGENT_HANDOFF.md               # Current state and next move for agents
    ARCHITECTURE.md                # Intended backend architecture
```

## Agent Handoff

Future agents should start with:

1. `docs/AGENT_HANDOFF.md`
2. `LabAssistant_Vision_and_Roadmap.md`
3. `docs/ARCHITECTURE.md`

The next best move is to validate the DLS importer against real CSV/XLS/XLSX
exports, especially real Orchestra summary workbooks plus matching intensity and
correlogram exports. Add fixture-based regression tests for any edge cases found.
