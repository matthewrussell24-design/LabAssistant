# Promote Related Experiment Search Into The Application Layer

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 011 - Promote Experiment Comparison

## Objective

Add a typed, versioned application query for finding related persisted DLS
samples and route the existing Streamlit workflow through it without changing
ranking behavior.

## Context

History listing, restore, and comparison already crossed the application
boundary. Similar-run search was the remaining history analysis called directly
by Streamlit and returned a mutable pandas DataFrame.

## Tasks

- Add immutable related-experiment result and match read models.
- Load persisted history inside the application query.
- Preserve feature weighting, ranking, exclusion, and similarity scores.
- Register the capability and route Streamlit through it.
- Test ranking, serialization, empty history, exclusion, and invalid limits.

## Deliverables

- `find_related_experiments` and its typed read models.
- Capability registration and Streamlit caller migration.
- Application tests and aligned architecture/status documentation.

## Success Criteria

The shell finds related saved samples through a versioned immutable application
contract and does not own ranking or persistence access.

## Implementation Summary

- Added frozen `RelatedExperiments` and `RelatedExperimentMatch` models.
- Added `find_related_experiments`, which loads history, delegates ranking to
  `history.find_similar_samples`, and translates the result into typed matches.
- Preserved the established distance, weight normalization, readable similarity
  score, record exclusion, and top-N ordering.
- Routed Streamlit through the application capability and registered the public
  capability name.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/012-promote-related-experiment-search.md`

## Test Results

- Focused application and history tests: 29 passed.
- Full suite: 146 passed in 2.11s (was 144; +2 application tests).
- Status-page links and `git diff --check` passed.

## Remaining Work

- Promote the history summary and trend read paths so Streamlit no longer loads
  JSONL history directly for those views.
- Generalize related-evidence search when another persisted technique has stable
  comparable features.
