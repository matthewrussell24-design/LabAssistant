# Promote DLS Angle Details

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 034 - Promote DLS Sample Summaries

## Objective

Promote per-angle DLS detail rows into an immutable application workflow while
preserving ordering, values, and empty-angle behavior.

## Context

Streamlit still calls the pandas-returning `build_angle_table` helper directly
for its secondary per-angle diagnostic.

## Tasks

- Accept parsed DLS samples without a caller-provided DataFrame.
- Preserve sample-major and angle-minor ordering.
- Return typed immutable count, replicate, Z-average, PDI, peak, and D50 values.
- Preserve valid empty rows when no angle summaries exist.
- Register the workflow and migrate Streamlit table rendering.

## Deliverables

- `retrieve_dls_angle_details` capability.
- Frozen angle-detail row and result read models.
- Streamlit migration and exact-row compatibility tests.

## Success Criteria

Streamlit renders per-angle detail from immutable typed rows and constructs a
DataFrame only for display.

## Implementation Summary

- Added frozen `DLSAngleDetailRow` and `DLSAngleDetails` contracts with semantic
  field names.
- Added `retrieve_dls_angle_details`, preserving sample-major and angle-minor
  ordering plus valid empty results.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit's per-angle detail through immutable rows while retaining
  column labels, numeric rounding, and DataFrame display in the UI.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/035-promote-dls-angle-details.md`

## Test Results

- Focused application, view-model, and model tests: 73 passed.
- Full suite: 193 passed in 2.57s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the shared DLS metrics projection into immutable application rows.
