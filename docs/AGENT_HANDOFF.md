# Agent Handoff

This file is the first stop for future agents. Keep it current whenever the
next best move changes.

## Current Objective

LabAssistant's strategic direction has broadened: it is an Experiment
Intelligence Platform that transforms laboratory data into scientific insight
across the lifecycle of a scientific experiment, not a DLS analyzer or primarily
a Zetasizer/DLS dashboard. The current Zetasizer/DLS workflow is the first
supported use case and must remain stable while the backend moves toward
experiment-first ingestion, metrics, reasoning, reporting, and memory.

Experiments are first-class objects. Measurements are building blocks. The
reasoning engine should compare observations across instruments and over time.
Reports should describe experiments, not datasets.

Phases 3, 4, and 5 all have working implementations validated against the real
Orchestra exports, and dual-angle protein aggregation detection is now the first
deep instrument-specific scientific interpretation feature. The next objective
is to preserve that workflow while introducing compatibility-first package
boundaries for the broader platform architecture.

Recently completed across the phases:

- Phase 3: full derived-metric engine plus dual-angle (forward/back) handling.
- Phase 4: decision-first dashboard now includes a Scattering Angle Breakdown
  section that appears only for dual-angle runs.
- Phase 5: local history with storage, trend charts, experiment comparison
  (Z-average / PDI drift vs the last saved run), and similar-run search.

The shared integration point is the Measurement-backed `ParsedSample` view
model, `build_metrics_table`, and `build_angle_table`.

## Current Project State

- `app.py` contains the working Streamlit dashboard, multi-file import preview,
  and chart rendering.
- `labassistant/importers/file_classifier.py` classifies uploads as summary,
  intensity distribution, correlogram, or unknown.
- `labassistant/importers/lot_grouper.py` normalizes project lot names. For this
  project, `446-01`, `Lot 446-01`, `Lyo 446-01`, and `Lot 1` all normalize to
  `lot_1` and display as `Lot 1`.
- `labassistant/importers/measurement_importer.py` builds the preview table and
  merges each lot into one `Measurement`.
- `labassistant/history.py` stores saved experiments in local JSONL history
  under `.labassistant_history/experiments.jsonl`.
- Imported samples are cached in `st.session_state` by uploaded-file batch
  signature. This prevents Streamlit widget reruns, such as changing the
  reference sample, from dropping back to the import button.
- `README.md` frames LabAssistant as a laboratory intelligence platform and
  summarizes current DLS capabilities.
- `docs/VISION.md` is the canonical product vision.
- `docs/ROADMAP.md` is the canonical incremental platform roadmap.
- `docs/ARCHITECTURE.md` describes the intended instrument-agnostic module
  boundaries and migration guardrails.
- `LabAssistant_Vision_and_Roadmap.md` is now a compatibility pointer to the
  split docs.

## Next Best Move

The safest next move is a compatibility-first refactor that introduces
experiment-centered boundaries without breaking the current Zetasizer workflow:

1. Add a first-class `Experiment` model/envelope around the existing
   `Measurement` list and history record payloads.
2. Add `labassistant/ingestion/zetasizer.py` as a facade over the existing DLS
   importer and multi-file import flow.
3. Add `labassistant/reasoning/experiment_brief.py` as a facade over the current
   decision brief logic in `interpretation.py`.
4. Add `labassistant/reasoning/reproducibility.py` for pure percent-RSD/outlier
   helpers currently living in `trend_analysis.py`, keeping old imports working.
5. Add `labassistant/particle_size_metrics.py` behind the existing
   `labassistant/metrics.py` compatibility module; later convert to
   `metrics/particle_size.py` when callers are ready.
6. Add compatibility tests proving old and new import paths both work.

After that, two lanes remain open:

### Phase 3 Lane

The derived-metric engine and real-file validation are now done (see
"Completed Phase 3 metric engine work" and "Validated against real data"
below). Real Orchestra exports for lots 446-01/02/03 parse end-to-end, and
trimmed Lot 1 fixtures under `tests/fixtures/` lock in the values via
`tests/test_real_fixtures.py`.

Dual scattering angle, measurement datetime, and per-angle replicate grouping
are now DONE (see "Completed Dual-Angle Work" below). Remaining follow-ups:

1. The lot-level `derived_metrics` (overall primary peak, D50, etc.) are still
   computed from intensity replicate 1 only. Per-angle metrics now live on
   `Measurement.angle_summaries`; consider whether the lot-level overall should
   instead summarize both angles or be de-emphasized in favor of the per-angle
   view now that it exists.
2. Render the per-angle view in the dashboard. `view_models.build_angle_table`
   returns a ready per-lot/per-angle table, and per-angle averaged curves are
   stored under `measurement.distributions["angle_forward"|"angle_back"]`.
3. Keep `app.py` focused on Streamlit rendering; keep analysis logic in
   `labassistant/`.

## Validated Against Real Data (2026-07-02)

Real exports for three lots (summary + intensity + correlogram each) were run
through `build_import_preview` and `import_measurement_groups`:

- Classification, lot normalization (`446-01` / `Lot 1`), and grouping produced
  three "Complete" lots with no errors.
- Summary metrics matched the Orchestra "Summary" stats block exactly
  (e.g. Lot 1 Z-average 359.14 nm, PDI 0.323, max Z 499.3, count 18).
- Derived metrics are sensible: single clean peaks ~420-660 nm, quality scores
  67-73 (PDI-driven), all Low aggregation risk.
- Trimmed Lot 1 files are committed under `tests/fixtures/`; do not delete them.

### Phase 5 Lane

Build history, trend analysis, and experiment comparison.

Recommended sequence:

1. Keep history storage Measurement-backed, not raw-upload backed.
2. Expand the current local JSONL store into comparison workflows for saved
   experiments.
3. Add tests before changing storage schema.
4. Keep `.labassistant_history/` out of git.

## After That

Once real-file importer validation and local history are stable:

1. Refactor remaining chart/table helper functions out of `app.py` where useful.
2. Add richer experiment comparison and similar-run search.
3. Consider migrating from JSONL to SQLite only when query needs justify it.

## Completed Phase 1 Work

- Added `labassistant/models.py` with dataclasses for `Measurement`,
  `MeasurementMetadata`, `DistributionData`, `SummaryMetrics`,
  `DerivedMetrics`, and `MeasurementFlag`.
- Added a conversion function that maps the current `ParsedSample` output into a
  `Measurement`.
- Kept the Streamlit UI working from existing `ParsedSample` structures.
- Added tests for model defaults, serialization, merging, and adapter mapping.
- Extracted pure metric functions into `labassistant/metrics.py` with tests for
  D10/D50/D90, tail index, width ratio, and peak detection.
- Extracted quality thresholds and status classification into
  `labassistant/quality.py` with focused tests.
- Extracted DLS table parsing, metadata extraction, summary detection, date
  handling, and column inference helpers into `labassistant/importers/dls.py`
  with importer tests.
- Added `ParsedDLSResult` and moved upload parsing orchestration into
  `parse_dls_upload`, leaving `app.py` as a compatibility wrapper for the
  current dashboard.
- Added `labassistant/measurements.py` for `ParsedDLSResult` to `Measurement`
  conversion.
- Added `labassistant/view_models.py` so the current dashboard uses
  Measurement-backed sample view models.
- Added `labassistant/interpretation.py` for decision brief, attention scoring,
  analyst summaries, and data-analysis text.
- Reduced `app.py` to Streamlit rendering and interaction code plus chart helper
  functions.
- Added multi-file import modules:
  `labassistant/importers/file_classifier.py`,
  `labassistant/importers/lot_grouper.py`, and
  `labassistant/importers/measurement_importer.py`.
- Added an import preview table with statuses: Complete, Missing summary,
  Missing intensity distribution, Missing correlogram, and Unknown files.
- Added project-specific lot normalization for `446-01`/`Lot 1` style names.
- Updated grouped `Measurement` creation so summary data supplies scalar
  metrics, intensity files supply graph/distribution-derived metrics, and
  correlogram files supply signal-quality data.
- Added focused tests in `tests/test_multi_file_importer.py`.
- Started Phase 4 dashboard redesign:
  - Added a dashboard-level health strip based on existing sample statuses.
  - Moved import preview and import action into the sidebar.
  - Collapsed import details after successful import, reopening automatically
    when import errors exist.
  - Made the post-import main surface start with Decision Brief, Health Score,
    AI Findings, Samples To Inspect, Primary Distribution Review, and Key Metric
    Comparison before sample cards or secondary diagnostics.
  - Added `render_primary_visualization`, `render_decision_workbench`,
    `render_health_strip`, and `render_import_details` in `app.py`.
- Fixed Python 3.9 test collection for `tests/test_multi_file_importer.py` by
  adding postponed annotations.
- Completed first Phase 5 pass:
  - Added `labassistant/history.py` for local JSONL experiment records.
  - Added `.labassistant_history/` to `.gitignore`.
  - Added sidebar save action for the current imported experiment.
  - Added an Experiment History panel with saved-run summary plus Z-average and
    PDI trend views.
  - Added `tests/test_history.py`.
- Fixed short-correlogram quality fallback in
  `labassistant/importers/measurement_importer.py` so synthetic and small
  correlogram fixtures still receive a noise score.

## Completed Phase 3 Metric Engine Work (2026-07-02)

- Added shape metrics to `labassistant/metrics.py`, all pure and unit-documented:
  - `count_peaks` — number of resolved modes.
  - `calculate_peak_width` — primary-peak FWHM as a geometric span ratio in
    log-size space; returns `None` when the peak is truncated at a data edge.
  - `calculate_peak_symmetry` — right/left half-width ratio at half maximum
    (>1 tails toward larger sizes).
  - `calculate_log_skewness` — intensity-weighted skewness of log10(diameter)
    (DLS is log-normal, so 0 = symmetric, + = large-particle tail).
  - `assess_aggregation_risk` — Low/Moderate/High from combined evidence
    (tail index, secondary-peak ratio and absolute size, PDI, skew, width).
  - `calculate_quality_score` — 0-100 heuristic screening score (penalizes high
    PDI, large-particle tail, broad width, secondary peak, correlogram noise).
- Reworked `_refresh_correlogram_quality` so `correlogram_noise_score` measures
  per-replicate baseline scatter (points below 10% of the intercept), averaged
  across replicates, instead of the whole-curve standard deviation. This makes
  the score a real noise/quality signal rather than a proxy for decay spread.
- Extended `DerivedMetrics` with `peak_count`, `peak_width_ratio`,
  `peak_symmetry`, and `skewness`; populated `aggregation_risk` and
  `quality_score` (previously unused).
- Wired the new metrics through `parse_dls_upload` (metrics dict),
  `measurement_from_dls_result`, and `_refresh_distribution_metrics_from_intensity`,
  and surfaced them in `view_models.sample_from_measurement` and
  `build_metrics_table`.
- Added `tests/test_metrics.py` cases for every new function (synthetic
  log-Gaussian, bimodal, edge-truncated, and sign-of-skew cases) and
  `tests/test_real_fixtures.py` regression tests over trimmed real exports.
- Note: `find_local_peaks` now also reports edge maxima (index 0 / last) above
  the 8% threshold; the new metrics were validated against this behavior.

## Completed Dual-Angle Work (2026-07-02)

The Orchestra exports are dual-angle runs (forward 12.78° + back 174.7°). The
importer now separates them instead of blending both into one Z-average.

- Added `AngleSummary` to `labassistant/models.py` and
  `Measurement.angle_summaries`; `merge()` now also (a) fills missing metadata
  scalars (`measurement_datetime`, instrument, temperature, scattering angle,
  etc.) — previously dropped on multi-file import — and (b) merges angle
  summaries by angle without duplicating.
- `dls.summarize_by_angle` groups the summary measurement table by scattering
  angle (robust to non-alternating order, e.g. Lot 3) into per-angle count,
  mean Z, mean PDI, and max Z. Attached to `ParsedDLSResult.angle_summaries`
  and mapped into the Measurement by `measurements.angle_summaries_from_result`.
- `measurement_importer._assign_replicates_to_angles` classifies each intensity
  replicate to the nearest angle (log-distance of its D50 to the per-angle mean
  Z), averages an angle's replicates into one curve, and stores per-angle
  primary peak / D50 plus `distributions["angle_forward"|"angle_back"]`.
- `view_models.build_angle_table` exposes a per-lot/per-angle table for the UI;
  `sample_from_measurement` now labels `Scattering Angles` from the angle data.
- Validated on real data: Lot 1 forward 453.1 nm / back 265.2 nm (matches the
  stats block); per-angle peaks forward 420 nm vs back 267 nm. `count`
  (measurements) and `replicate_count` (classified intensity curves) can differ
  when the intensity export is a subset (Lot 3: 12/13 measurements, 6/6 curves).
- Tests: `test_dls_importer` (angle grouping), `test_models` (metadata + angle
  merge), and `test_real_fixtures` (real dual-angle split).

## Completed Phase 4 + Phase 5 Follow-up (2026-07-02)

- Phase 4: added `render_angle_breakdown` in `app.py` and `_angle_bar_chart`. It
  renders a "Scattering Angle Breakdown" (per-angle table + forward/back
  Z-average and primary-peak grouped bars) after Key Metric Comparison, and only
  when `build_angle_table` is non-empty (i.e. a dual-angle run is present).
- Phase 5: added experiment comparison to `labassistant/history.py`:
  `latest_experiment`, `compare_experiments`, and `compare_to_history`. They
  match current samples to a previous saved run by sample name and report
  Z-average % change, PDI change, and a drift label ("Stable", "New sample",
  "Z-average drift", "PDI drift"). Thresholds: `Z_DRIFT_PERCENT = 20.0`,
  `PDI_DRIFT_ABSOLUTE = 0.10`. `latest_experiment` breaks same-second timestamp
  ties by append order (last saved wins).
- The Experiment History panel now shows a "Change vs last saved experiment"
  table above the saved-runs summary.
- Tests added in `tests/test_history.py` for drift, new-sample, and latest-run
  tie-breaking behavior.

## Similar-Run Search (2026-07-02)

- Added `find_similar_samples` in `labassistant/history.py`. It ranks every
  saved sample against a query `Measurement` by a weight-normalized distance:
  log10 ratio for size features (Z-average, primary peak) and absolute
  difference for PDI, using `SIMILARITY_WEIGHTS`. Only features present on both
  sides contribute; the score divides by the weight actually used. Returns a
  table sorted by `Distance` (ascending) with a 0-100 `Similarity` readability
  score (`100 * exp(-3 * distance)`, documented as heuristic, not a probability).
- Dashboard: the Experiment History panel has a "Find similar past runs"
  selector that matches a chosen current sample against saved history.
- Tests in `tests/test_history.py` cover ranking order, record exclusion, and
  the empty-history case.

## Dual-Angle Aggregation Detection (2026-07-02)

Headline scientific feature implementing Malvern application notes AN101104 /
AN140527. Do not treat it as a minor metric.

- `labassistant/aggregation.py`: `assess_dual_angle_aggregation(measurement)`
  returns a `DualAngleAggregation` with the Aggregation Index
  (`Z_forward / Z_backscatter - 1`), the identified forward (~12.8°) and
  backscatter (~173°) angle summaries, level (None/Low/Moderate/High via
  thresholds `INDEX_WATCH=0.05`, `INDEX_ELEVATED=0.10`, `INDEX_HIGH=0.30`),
  forward-angle tail/secondary-peak evidence, correlogram-noise confidence,
  flags, and a plain-language summary. Uses summary Z per angle for the index,
  the forward per-angle distribution for aggregate evidence, and
  `correlogram_noise_score` for confidence.
- `DerivedMetrics.aggregation_index` is populated in
  `measurement_importer._apply_dual_angle_aggregation`, which also adds a
  review-level "Dual-angle aggregation" flag when elevated (registered in
  `quality.REVIEW_WARNINGS`) and stores the full assessment under
  `provenance["dual_angle_aggregation"]`.
- Surfaced in `view_models` (metrics dict + `build_metrics_table`) and rendered
  prominently at the top of the dashboard by `render_aggregation_detection` in
  `app.py` (index cards, forward-vs-back Z chart, index chart with threshold
  lines, paired per-angle intensity overlay, flags, and explanation).
- Real data: all three lots show an elevated index (~0.71-0.86, level High) with
  High confidence — forward Z ~450-530 nm vs backscatter ~265-285 nm.
- Tests: `tests/test_aggregation.py` (index, angle-pair ID, thresholds, flags,
  unavailable case) and a real-fixture assertion in `tests/test_real_fixtures.py`.
- Caveat carried in the copy: these lots are already large (~265 nm backscatter),
  so a high index reflects a strong forward-angle size excess to corroborate with
  orthogonal methods, not necessarily monomer->aggregate conversion.

### Corroboration refinement (2026-07-02)

- `DualAngleAggregation` now carries a corroboration checklist (`checks`), a
  `corroboration_score`/`corroboration_max`, an interpretation `category`, a
  `headline`, and a `recommendation`. `assess_dual_angle_aggregation` evaluates
  five evidence areas: (1) index magnitude, (2) forward vs backscatter
  Z-average, (3) forward distribution evidence — large-particle tail, secondary
  peak, forward-vs-back peak shift, (4) correlogram confidence — baseline noise
  and decay quality (`_decay_quality` from mean intercept), (5) replicate
  consistency across angles (`_replicate_consistency` from per-angle D50 CV,
  stored by `_assign_replicates_to_angles` in
  `provenance["angle_replicate_d50s"]`).
- Categories: Low signal / Watch / Elevated / Strong signal, corroborated /
  Strong signal, repeat recommended. The Strong band splits on confidence +
  independent evidence. Constants: `INDEX_WATCH/ELEVATED/HIGH`,
  `PEAK_SHIFT_SUPPORT_RATIO`, `FORWARD_TAIL_SUPPORT`, `REPLICATE_CV_CONSISTENT`,
  `DECAY_INTERCEPT_GOOD/MODERATE`.
- Phrasing is deliberately non-definitive (never "proof"): "Strong dual-angle
  aggregation signal", "Forward-angle large-species enrichment", "Requires
  corroboration", "Recommend review / repeat / orthogonal confirmation".
- Dashboard: cards show category + corroboration score; a per-sample
  corroboration checklist (supports/neutral/insufficient) plus headline and
  recommendation render below the paired overlay.
- The Malvern Aggregation Index calculation itself is unchanged.
- Real data: Lots 1 and 2 -> "Strong signal, corroborated" (4/6, High
  confidence); Lot 3 -> corroborated but with Variable replicates surfaced. The
  trimmed Lot 1 fixture -> "repeat recommended" (one backscatter replicate,
  shorter correlogram baseline), which the real-fixture test allows.
- Tests: category bands, corroborated vs repeat paths, and checklist coverage in
  `tests/test_aggregation.py`.

## Known follow-ups

- Lot-level `derived_metrics` still come from intensity replicate 1; the
  per-angle view on `angle_summaries` is the richer signal now.
- Parser/dashboard edge-case polish on additional real exports (other software
  versions, single-angle runs, volume/number distributions) is still open.

## Known Risks

- The parser currently uses flexible heuristics for messy instrument exports.
  Small changes can silently alter what table is selected.
- Real Malvern exports may vary by software version, locale, delimiter,
  workbook sheet layout, and copied graph format.
- Filename classification is heuristic. When real files disagree with the
  current rules, add regression tests before changing classifier or lot logic.
- Do not put post-import chart controls behind a transient `st.button` branch.
  Streamlit buttons are only true for one rerun; use the cached imported samples
  after the initial import.
- The current code has limited automated tests, so validate parser changes with
  both synthetic and real representative files.
- Local history currently stores full `Measurement.to_dict()` payloads as JSONL.
  Treat that as an early schema; add migration care before changing keys.

## Working Rules for Agents

- Read `docs/VISION.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, this file,
  and `README.md` before making architectural changes.
- Check `git status --short` before editing. Preserve user or previous-agent
  changes.
- Keep changes scoped to the current milestone.
- Prefer extracting pure logic with tests over redesigning the UI.
- Update this file when you finish a milestone or discover a better next move.
- If you add a new module, add or update tests in the same turn whenever
  practical.

## Validation Checklist

Before handing off:

- Run any available tests.
- If UI behavior changed, start Streamlit and smoke test the empty state.
- Confirm imports work from a clean Python process.
- Update docs if the next best move changed.
- Leave `git status --short` understandable.
