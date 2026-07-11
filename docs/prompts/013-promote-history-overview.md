# Promote History Overview Into The Application Layer

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 012 - Promote Related Experiment Search

## Objective

Add a typed, versioned application query for persisted experiment summaries and
sample trends, then route the Streamlit History panel through it without
changing table or plotting behavior.

## Tasks

- Add immutable history summary, trend point, and overview read models.
- Load persisted history and derive existing summary/trend metrics in the application query.
- Register the capability and remove direct JSONL reads from the History panel.
- Preserve append ordering, status counts, medians, empty states, and plots.
- Test serialization, representative metrics, missing history, and empty experiments.

## Implementation Summary

- Added `retrieve_history_overview` with frozen summary and trend read models.
- Reused the established history derivations and translated their DataFrames at the boundary.
- Routed Streamlit history tables, comparison baseline selection, trends, and saved-record
  browsing through application capabilities.

## Success Criteria

The Streamlit History panel receives persisted summary and trend evidence
through immutable application contracts without reading JSONL directly.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/013-promote-history-overview.md`

## Test Results

- Focused application tests: 22 passed.
- Full suite: 148 passed.
- Python compilation through the project test environment, `git diff --check`,
  status-page links, and graph update passed.

## Remaining Work

- Generalize persisted restore for a second technique, starting with chromatography.
