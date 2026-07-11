# Promote Persisted Experiment Saving

Status: Complete
Created: 2026-07-11
Last Updated: 2026-07-11
Priority: High
Depends On: 021 - Promote Filtration CSV Import

## Objective

Promote the explicitly confirmed experiment-history write into a validated
application command with immutable receipt metadata.

## Tasks

- Validate that at least one serializable measurement is present.
- Preserve normalized append-only labels and loaded-record lineage provenance.
- Persist copied evidence so saving does not mutate the active experiment.
- Return immutable record identity, timestamp, label, evidence count, and lineage metadata.
- Register the command for Human UI and CLI callers only and migrate Streamlit.

## Success Criteria

Streamlit's Save Current Experiment button calls a registered application
command and no longer imports the JSONL history writer; autonomous and future-API
write access remains excluded.

## Implementation Summary

- Added a frozen, versioned experiment-history save receipt.
- Added `save_experiment_history` with evidence validation, label normalization,
  copied lineage annotation, and one append-only local history write.
- Registered the command for Human UI and CLI callers only.
- Routed Streamlit's confirmed save action through the application command and
  removed its direct history-writer import and live-measurement mutation.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/022-promote-experiment-history-save.md`

## Test Results

- Focused application tests: 40 passed.
- Full suite: 168 passed in 2.44s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote normalized observation generation into an explicit application
  workflow so interface shells do not coordinate observation helpers directly.
