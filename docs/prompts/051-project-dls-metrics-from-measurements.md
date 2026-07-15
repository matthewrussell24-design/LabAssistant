# Project DLS Metrics From Measurements

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 050 - Stabilize The DLS Evidence Input Contract

## Objective

Make shared DLS metrics and status derive from authoritative `Measurement`
evidence rather than the mutable workspace metrics dictionary.

## Context

Task 050 removed reusable-core imports of the legacy view-model facade, but the
neutral evidence protocol still exposes compatibility metrics. The immutable
application metrics read and shared pandas compatibility table both read that
dictionary even though the same values live in Measurement fields, flags,
metadata, and provenance.

## Tasks

- Add a frozen, pandas-free Measurement-to-metrics projection.
- Preserve data-type, scattering-angle, warning/status, and optional metric
  semantics from imported and restored evidence.
- Route `retrieve_dls_metrics` and `build_metrics_table` through the projection.
- Keep pandas construction confined to the compatibility table helper.
- Update synthetic fixtures to construct authoritative Measurement evidence.
- Prove mutable workspace metrics cannot override the application projection.

## Deliverables

- `DLSMeasurementMetrics` and `measurement_metrics`.
- Measurement-first application and compatibility metrics projections.
- Regression coverage for field mapping, status, column order, and divergence.

## Success Criteria

`retrieve_dls_metrics` and `build_metrics_table` do not read `sample.metrics`,
existing scientific outputs remain stable, and application results remain
immutable and pandas-free.

## Implementation Summary

- Added frozen `DLSMeasurementMetrics` and a pure `measurement_metrics`
  projection over authoritative Measurement summary/derived metrics, metadata,
  flags, and provenance.
- Preserved original single-file data types and explicit reconstructed-workspace
  data types through Measurement provenance.
- Routed `build_metrics_table`, `sample_status`, and `retrieve_dls_metrics`
  through the shared projection while keeping pandas out of the application
  result.
- Updated synthetic fixtures so their Measurement evidence matches UI
  compatibility fields.
- Added divergence coverage proving mutable `sample.metrics` overrides cannot
  alter either application or compatibility metric projections.

## Files Changed

- `labassistant/dls_evidence.py`
- `labassistant/application.py`
- `labassistant/__init__.py`
- `tests/test_application.py`
- `tests/test_interpretation.py`
- `tests/test_observations.py`
- `tests/test_trend_analysis.py`
- `tests/test_view_models.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/051-project-dls-metrics-from-measurements.md`

## Test Results

- Focused projection and compatibility coverage: 6 passed in 0.85s.
- Full suite: 227 passed in 2.81s.
- Python compile verification, status-page link checks, and `git diff --check`
  passed.
- Headless Streamlit startup and health smoke passed on port 8765.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Route review-evidence formatting and immutable DLS sample summaries through
  `DLSMeasurementMetrics`, preserving exact wording and optional display rows.
