# Promote DLS Metrics Projection

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 035 - Promote DLS Angle Details

## Objective

Promote the shared DLS metrics projection into immutable application rows while
preserving the established schema, values, statuses, warnings, and sample order.

## Context

Streamlit still calls the pandas-returning `build_metrics_table` helper directly
and shares that DataFrame across comparison charts, diagnostic visualizations,
raw-data display, and CSV export.

## Tasks

- Accept parsed DLS samples without a caller-provided DataFrame.
- Preserve sample ordering, metric values, optional fields, statuses, and warning
  evidence.
- Return typed immutable metric rows through a registered application workflow.
- Reconstruct the established display DataFrame only in the Streamlit shell.
- Add exact compatibility, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_metrics` capability.
- Frozen DLS metric row and result read models.
- Streamlit migration with the existing display and export schema preserved.

## Success Criteria

Streamlit obtains its shared DLS metric rows through the application boundary,
constructs pandas only in the shell, and preserves existing chart and table
behavior.

## Implementation Summary

- Added frozen `DLSMetricRow` and `DLSMetricsProjection` contracts with semantic
  field names, immutable warning evidence, and unchanged optional values.
- Added and registered `retrieve_dls_metrics`, preserving sample order, status,
  metrics, measurement metadata, and warning order without returning pandas.
- Routed Streamlit's shared chart, diagnostic, raw-table, and CSV-export
  DataFrame through the immutable projection while preserving all 27 existing
  display columns exactly.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/036-promote-dls-metrics-projection.md`

## Test Results

- Focused application, view-model, and multi-file importer tests: 76 passed.
- Full suite: 195 passed in 2.36s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote the DLS distribution-series visualization projection into immutable
  application data without moving Plotly or UI selection state into the
  application layer.
