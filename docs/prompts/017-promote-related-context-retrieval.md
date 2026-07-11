# Promote Related Scientific Context Retrieval

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 016 - Promote Experiment Investigation

## Objective

Expose deterministic local-memory context retrieval through an immutable,
versioned application contract and route Streamlit's context panel through it.

## Tasks

- Add immutable context-item and packet read models with stable provenance.
- Preserve keyword ranking, tag filters, result limits, confidence, caveats, and missing-information behavior.
- Keep arbitrary mutable knowledge payloads behind the boundary.
- Register `retrieve_related_context` and migrate the Streamlit caller.
- Test populated, filtered, empty, serialized, and invalid requests.

## Success Criteria

The Streamlit context panel receives related scientific context through a
registered application query without constructing `ContextRetriever` itself.

## Implementation Summary

- Added frozen scientific-context item and packet read models with stable IDs,
  experiment/project/instrument/source provenance, tags, confidence, and timestamps.
- Added and registered `retrieve_related_context`, preserving deterministic
  ranking, tag filtering, limits, confidence, caveats, and missing information.
- Kept arbitrary mutable knowledge payload dictionaries behind the boundary.
- Routed Streamlit's memory context panel through the application query and
  removed its direct `ContextRetriever` construction.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/017-promote-related-context-retrieval.md`

## Test Results

- Focused application and context-engine tests: 36 passed.
- Full suite: 158 passed in 2.10s.
- Headless Streamlit startup smoke passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote Research Journal read/filter/export workflows into application-layer
  contracts while keeping note creation an explicit reviewed write.
