# Promote DLS Health Overview

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 028 - Promote DLS Data Analysis

## Objective

Promote the DLS health overview into an immutable application read model while
preserving the current screening weights, status counts, and metric medians.

## Context

All established DLS narrative builders cross the application boundary, but
Streamlit still calculates its compact health strip from parsed samples and a
pandas metrics table.

## Tasks

- Accept parsed DLS samples without requiring a caller-provided DataFrame.
- Preserve Normal/Watch/Review score weights of 100/65/25.
- Return immutable sample, flagged, review, and median metric values.
- Keep display formatting and card layout in Streamlit.
- Register the workflow and migrate the health strip.

## Deliverables

- `summarize_dls_health` capability.
- Frozen `DLSHealthOverview` read model.
- Streamlit migration and compatibility tests.

## Success Criteria

Streamlit renders its DLS health strip through one registered application
workflow and no longer computes the screening score, status counts, or medians.

## Implementation Summary

- Added frozen, versioned `DLSHealthOverview` with a clearly named screening
  score, status counts, and raw median values.
- Added `summarize_dls_health`, preserving Normal/Watch/Review weights of
  100/65/25 and building metrics internally.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit's health strip through the application result and removed
  its score, count, and median calculations.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/029-promote-dls-health-overview.md`

## Test Results

- Focused application, view-model, and interpretation tests: 55 passed.
- Full suite: 181 passed in 2.41s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote DLS control-chart and replicate-statistics tables into immutable
  application read models.
