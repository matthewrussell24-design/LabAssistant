# Migrate Saved DLS Workspace Restore

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 044 - Promote DLS Filtration Evidence

## Objective

Migrate the Streamlit saved DLS workspace loader to a technique-aware
application workflow without reconstructing parsed samples in the shell.

## Context

The saved-run loader still retrieves raw persisted measurements and calls
`sample_from_measurement` in Streamlit. The native desktop already uses the
read-only `restore_dls_experiment` composition, but its `DLSAnalysisResult`
should remain presentation-oriented rather than expose editable samples.

## Tasks

- Add a dedicated workspace restore result with copy-on-access parsed samples.
- Preserve immutable saved-record metadata, source files, import errors, and
  the existing read-only native restore result.
- Reuse the technique-aware DLS restoration composition without a second JSONL
  retrieval or duplicated reconstruction logic.
- Route the explicit Streamlit load action through the workspace restore
  workflow while preserving session keys, labels, lineage, errors, and rerun.
- Add compatibility, immutability, provenance, and malformed-record coverage.

## Deliverables

- `restore_dls_workspace` application workflow.
- Frozen `DLSWorkspaceRestoreResult` with fresh editable sample restoration.
- Streamlit saved-experiment loader migration.

## Success Criteria

Streamlit restores saved DLS workspace samples through the technique-aware
application workflow without importing persisted-measurement retrieval or the
measurement-to-sample conversion helper.

## Implementation Summary

- Added a frozen `DLSWorkspaceRestoreResult` that combines the existing
  read-only analysis, immutable saved-record metadata, and copy-on-access
  parsed samples without exposing editable evidence in serialized output.
- Factored one internal DLS reconstruction path so native analysis restore and
  editable workspace restore share a single persisted read and preserve source
  files, history provenance, validation, and error behavior.
- Migrated Streamlit's explicit load action to the workspace workflow while
  retaining session keys, updated-label behavior, import errors, and rerun.
- Removed Streamlit imports of `retrieve_experiment` and
  `sample_from_measurement`.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/045-migrate-saved-dls-workspace-restore.md`

## Test Results

- Focused DLS restore tests: 5 passed.
- Full suite: 215 passed in 2.00s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote the reviewed scientific-memory save workflow so Streamlit does not
  assemble and mutate DLS or chromatography `Experiment` objects for storage.
