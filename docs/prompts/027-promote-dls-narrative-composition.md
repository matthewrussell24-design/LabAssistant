# Promote DLS Narrative Composition

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 026 - Promote DLS Decision Ranking

## Objective

Promote DLS automated findings and data-story composition into one immutable
application workflow while preserving the established deterministic wording.

## Context

DLS decision ranking crosses the application boundary, but Streamlit still
calls `build_ai_summary` and `build_data_story` directly and passes pandas
tables into both helpers.

## Tasks

- Accept parsed DLS samples without requiring callers to construct a DataFrame.
- Delegate narrative generation to the established interpretation and trend helpers.
- Return ordered immutable headings and bullet lists without pandas.
- Register one workflow and migrate both Streamlit narrative blocks to it.
- Preserve the explicit rule-based, non-AI presentation boundary.

## Deliverables

- `compose_dls_narrative` capability.
- Frozen narrative-section and DLS-narrative read models.
- Streamlit migration and compatibility tests for exact narrative output.

## Success Criteria

Streamlit renders its DLS automated findings and data story through one
registered application capability and no longer imports either narrative builder.

## Implementation Summary

- Added immutable `DLSNarrativeSection` and `DLSNarrative` contracts.
- Added `compose_dls_narrative`, which validates parsed samples, builds metrics
  internally, delegates to the existing deterministic builders, and preserves
  their section and bullet order.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Composed the narrative once per Streamlit dataset and passed the shared result
  to both Automated Findings and Data Story renderers.
- Preserved the explicit rule-based, non-language-model caption.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/027-promote-dls-narrative-composition.md`

## Test Results

- Focused application, interpretation, and trend tests: 63 passed.
- Full suite: 179 passed in 2.57s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the detailed DLS `build_data_analysis` composition so Streamlit no
  longer calls the remaining interpretation builder directly.
