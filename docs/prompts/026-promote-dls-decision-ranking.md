# Promote DLS Decision Ranking

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 025 - Promote Uploaded DLS Import Preview

## Objective

Promote DLS-specific screening rank into an immutable application workflow while
preserving the established scorer, warning thresholds, and tie-breaking behavior.

## Context

Uploaded DLS evidence and the generic Experiment Brief crossed application
contracts, but Streamlit's Decision Brief still called the pandas-returning
`build_decision_brief` helper directly.

## Tasks

- Accept parsed DLS samples without requiring callers to construct a DataFrame.
- Delegate scoring and change detection to the established interpretation helper.
- Return immutable best/attention candidates, counts, guidance, and ranked rows.
- Keep DLS screening separate from the instrument-independent Investigator.
- Register the workflow and migrate Streamlit's Decision Brief.

## Deliverables

- `rank_dls_decisions` capability.
- Frozen attention-row and decision-ranking read models.
- Streamlit migration and compatibility tests for flagged ranking and ties.

## Success Criteria

Streamlit renders its DLS Decision Brief through one registered application
capability, no longer imports `build_decision_brief`, and receives no pandas
object from the application boundary.

## Implementation Summary

- Added immutable `DLSAttentionRow` and `DLSDecisionRanking` contracts.
- Added `rank_dls_decisions`, which validates parsed samples, builds metrics
  internally, delegates to the existing deterministic scorer, and converts its
  ordered result into immutable rows.
- Registered the DLS-specific workflow for Human UI, CLI, and Future API callers
  while excluding Agent access.
- Routed Streamlit's Decision Brief cards, status message, and ranking table
  through the application result and removed its direct builder import.
- Added coverage for warning rank, flagged counts, next-check guidance,
  alphabetical tie-breaking, validation, and capability policy.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/026-promote-dls-decision-ranking.md`

## Test Results

- Focused application and interpretation tests: 50 passed.
- Full suite: 177 passed in 2.36s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the remaining DLS data-story/summary composition so Streamlit no
  longer coordinates `build_ai_summary` and related interpretation helpers directly.
