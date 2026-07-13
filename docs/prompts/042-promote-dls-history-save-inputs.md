# Promote DLS History Save Inputs

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 041 - Promote DLS History Inputs

## Objective

Let the explicit experiment-history save command accept parsed DLS samples
directly while preserving append-only writes, defensive copying, loaded-record
lineage, label normalization, receipts, validation, and explicit user action.

## Context

History reads now accept parsed samples, but Streamlit still unwraps every
sample's mutable measurement before invoking the reviewed save command.

## Tasks

- Resolve parsed-sample inputs to their measurement evidence inside the
  application boundary.
- Preserve established serializable-measurement callers, including non-DLS
  evidence accepted by the generic history writer.
- Copy resolved evidence before attaching loaded-record lineage.
- Keep button confirmation, labels, loaded-record session state, and success
  messaging in Streamlit.
- Add parsed-sample append, lineage, receipt, and mutation-safety coverage.

## Deliverables

- Parsed-sample input support for `save_experiment_history`.
- Streamlit save-call migration.
- Updated architecture and handoff documentation.

## Success Criteria

Streamlit submits parsed DLS samples directly to the existing reviewed history
command without mutating active analysis evidence or changing append semantics.

## Implementation Summary

- Added a shared internal resolver for direct measurement evidence and parsed
  samples, reused by DLS history reads and the reviewed save command.
- Resolved all save inputs before validation and one defensive copy, then added
  lineage only to copied evidence.
- Migrated the Streamlit save button to submit parsed samples directly while
  preserving confirmation, labels, loaded-record context, and success messaging.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/042-promote-dls-history-save-inputs.md`

## Test Results

- Focused application and history tests: 88 passed.
- Full suite: 207 passed in 2.41s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote reviewed circulation-time attachment and retrieval behind
  parsed-sample application workflows while retaining session state in
  Streamlit.
