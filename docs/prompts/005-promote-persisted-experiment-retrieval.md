# Promote Persisted Experiment Retrieval

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 004 - Define the LabAssistant Capability Layer

## Objective

Promote JSONL-backed experiment retrieval into the application capability
layer and make the existing Streamlit saved-experiment loader its first caller.

## Context

The Streamlit shell currently reconstructs saved measurements itself even
though `labassistant.history` already owns that behavior. Retrieval is the
first candidate read capability and should preserve the current JSONL schema,
session-state behavior, and editable loaded workspace.

## Tasks

- Add explicit single-record lookup with not-found and malformed-record errors.
- Add a typed, read-only application result that preserves history provenance
  and returns fresh editable measurement copies to callers.
- Register the retrieval capability and route the Streamlit loader through it.
- Add focused history, application, and integration coverage.
- Update capability and project-status documentation.

## Deliverables

- Persisted experiment retrieval capability and contract.
- Streamlit saved-experiment loader using the application boundary.
- Regression tests and aligned documentation.

## Success Criteria

Saved DLS experiments load through a registered capability without duplicating
history deserialization. Missing and malformed records are distinct, returned
measurements preserve provenance, callers cannot mutate the capability's stored
state, and the existing workflow remains compatible.

## Implementation Summary

- Added strict single-record JSONL lookup with distinct missing and malformed
  errors while preserving tolerant history browsing.
- Added a frozen `RetrievedExperiment` application contract whose metadata is
  serializable and whose measurement restoration returns fresh editable copies.
- Registered `retrieve_experiment` and routed the Streamlit saved-experiment
  loader through it, removing duplicate deserialization from the UI.
- Preserved loaded-history and version-lineage provenance without changing the
  JSONL schema.

## Files Changed

- `labassistant/history.py`
- `labassistant/application.py`
- `labassistant/__init__.py`
- `app.py`
- `tests/test_history.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/prompts/005-promote-persisted-experiment-retrieval.md`
- `docs/status/current-state.md`

## Test Results

- Focused history and application tests: 18 passed.
- Full suite: 124 passed in 2.40s.
- Streamlit headless startup: successful on port 8765.

## Remaining Work

- Keep JSONL browsing tolerant; consider broader corruption reporting only when
  the human history browser gains a reviewed error UX.
- Continue with canonical lot-level DLS derived metrics.
