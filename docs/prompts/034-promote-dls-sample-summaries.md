# Promote DLS Sample Summaries

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 033 - Promote DLS Aggregation Assessment

## Objective

Promote per-sample DLS status, warning evidence, and inspection values into an
immutable presentation-neutral application workflow.

## Context

Dataset-level DLS reasoning crosses application contracts, but Streamlit still
composes sample cards and “Samples To Inspect” content directly from mutable
parsed samples.

## Tasks

- Accept parsed DLS samples and preserve input ordering.
- Delegate status, review evidence, and scientific formatting to established helpers.
- Return immutable ordered label/value rows without HTML or layout details.
- Preserve conditional primary-peak/tail rows and missing-value behavior.
- Register the workflow and migrate both Streamlit sample-summary views.

## Deliverables

- `summarize_dls_samples` capability.
- Frozen metric-row, sample-summary, and collection read models.
- Streamlit migration and exact-output compatibility tests.

## Success Criteria

Streamlit renders sample cards and “Samples To Inspect” from one registered
immutable result without directly composing status or warning evidence.

## Implementation Summary

- Added frozen `DLSMetricDisplayRow`, `DLSSampleSummary`, and
  `DLSSampleSummaries` contracts.
- Added `summarize_dls_samples`, which preserves input ordering and delegates
  status, review evidence, and scientific formatting to established helpers.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit sample cards and “Samples To Inspect” through one shared
  immutable result while retaining all HTML and layout in the UI.
- Preserved optional primary-peak/tail rows, warning text, and missing values.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/034-promote-dls-sample-summaries.md`

## Test Results

- Focused application, interpretation, and view-model tests: 65 passed.
- Full suite: 191 passed in 2.34s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote DLS per-angle detail rows into an immutable application workflow.
