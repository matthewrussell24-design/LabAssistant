# Promote Filtration Follow-Up Trends

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 031 - Promote DLS Forward-Scatter Trends

## Objective

Promote filtration follow-up trend analysis into an immutable application
workflow while preserving attached evidence, Spearman relationships, and
correlation-only qualification.

## Context

Streamlit attaches reviewed manual or CSV filtration evidence to DLS
measurements, but still calls the mutable filtration trend builder directly.

## Tasks

- Accept parsed DLS samples carrying reviewed filtration provenance.
- Delegate analysis to the established filtration trend helper.
- Return immutable points and three relationship summaries.
- Preserve insufficient-data and correlation-only messages.
- Register the workflow and migrate Streamlit analysis/rendering.

## Deliverables

- `analyze_filtration_follow_up_trends` capability.
- Frozen filtration point, relationship, and result read models.
- Streamlit migration and compatibility tests.

## Success Criteria

Streamlit renders filtration trend tables, plots, and summaries through one
registered immutable application result while retaining reviewed input and
evidence attachment.

## Implementation Summary

- Added frozen `FiltrationTrendPointRead`, `FiltrationRelationshipSummary`, and
  `FiltrationTrendRead` contracts.
- Added `analyze_filtration_follow_up_trends`, which consumes reviewed
  measurement provenance, delegates to the established helper, and freezes its
  points and three qualified Spearman summaries.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit trend tables, plots, and summaries through the immutable
  result while retaining reviewed manual/CSV evidence attachment in the UI.
- Preserved exact insufficient-data and correlation-only messages.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/032-promote-filtration-trends.md`

## Test Results

- Focused application, trend, and filtration tests: 76 passed.
- Full suite: 187 passed in 2.56s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote dual-angle DLS aggregation assessment into an immutable application
  workflow.
