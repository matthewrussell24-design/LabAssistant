# Promote DLS Trend Diagnostics

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 029 - Promote DLS Health Overview

## Objective

Promote DLS control-chart and replicate-statistics diagnostics into one
immutable application workflow while preserving established calculations,
ordering, and zone labels.

## Context

DLS health and narrative summaries cross application contracts, but Streamlit
still calls pandas-returning trend table helpers directly.

## Tasks

- Accept parsed DLS samples without a caller-provided DataFrame.
- Delegate calculations to the established trend helpers.
- Return typed immutable control-chart and replicate-statistics rows.
- Compose diagnostics once per dataset and migrate both Streamlit views.
- Keep plotting, widgets, formatting, and display DataFrames in Streamlit.

## Deliverables

- `analyze_dls_trend_diagnostics` capability.
- Frozen diagnostic result and row read models.
- Streamlit migration and exact-row compatibility tests.

## Success Criteria

Streamlit renders control-chart and replicate diagnostics through one registered
application workflow and no longer imports either pandas-returning table helper.

## Implementation Summary

- Added frozen `DLSControlChartRow`, `DLSReplicateStatisticsRow`, and
  `DLSTrendDiagnostics` read models with semantic field names.
- Added `analyze_dls_trend_diagnostics`, which builds metrics internally,
  delegates to the established pandas helpers, and converts ordered rows.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Composed diagnostics once per Streamlit dataset and routed both the control
  chart and replicate-statistics table through the shared result.
- Preserved DataFrame construction only as a presentation concern.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/030-promote-dls-trend-diagnostics.md`

## Test Results

- Focused application and trend tests: 66 passed.
- Full suite: 183 passed in 2.31s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote DLS forward-scatter/circulation trend analysis into an immutable
  application workflow.
