# Promote DLS Forward-Scatter Trends

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 030 - Promote DLS Trend Diagnostics

## Objective

Promote DLS forward-scatter/circulation trend analysis into an immutable
application workflow while preserving explicit input provenance, relationship
statistics, and correlation-only language.

## Context

Streamlit captures reviewed circulation inputs and persists them on measurements,
but it still calls the mutable forward-scatter trend builder directly.

## Tasks

- Accept parsed DLS samples carrying reviewed circulation-time provenance.
- Delegate analysis to the established measurement-backed trend helper.
- Return immutable points and relationship summaries.
- Preserve insufficient-data messages and correlation-only qualification.
- Register the workflow and migrate Streamlit analysis/rendering.

## Deliverables

- `analyze_dls_forward_scatter_trends` capability.
- Frozen point, relationship, and result read models.
- Streamlit migration and compatibility tests.

## Success Criteria

Streamlit requests a typed forward-scatter trend result through one registered
application workflow while retaining only input widgets, reviewed evidence
attachment, and visualization.

## Implementation Summary

- Added frozen `DLSForwardScatterPoint`, `DLSRelationshipSummary`, and
  `DLSForwardScatterTrendRead` contracts.
- Added `analyze_dls_forward_scatter_trends`, which consumes reviewed
  measurement provenance, delegates to the established helper, and freezes its
  evidence and qualified relationship summaries.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit analysis through the application result while leaving
  session-state input, evidence attachment, formatting, and charts in the UI.
- Preserved exact insufficient-data and correlation-only messages.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/031-promote-dls-forward-scatter-trends.md`

## Test Results

- Focused application and trend tests: 68 passed.
- Full suite: 185 passed in 2.78s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote filtration follow-up trend analysis into an immutable application
  workflow.
