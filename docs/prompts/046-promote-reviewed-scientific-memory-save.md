# Promote Reviewed Scientific Memory Save

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 045 - Migrate Saved DLS Workspace Restore

## Objective

Promote reviewed scientific-memory saves so Streamlit submits current DLS
samples or a chromatography analysis result without assembling or mutating
domain `Experiment` objects in the shell.

## Context

The memory persistence operation is already in the application layer, but the
Streamlit shell still builds a DLS experiment, restores a chromatography
experiment, mutates the selected experiment label, and passes that mutable
domain object into the command.

## Tasks

- Extend the existing reviewed memory command to accept `Experiment`, parsed
  DLS samples, or `ChromatographyAnalysisResult` evidence.
- Assemble or defensively copy the selected experiment before applying a label.
- Preserve label fallback, source provenance, observations, hypotheses,
  recommendations, tags, optional project ID, human note, and injected stores.
- Return a frozen, versioned receipt for explicit UI confirmation.
- Keep established direct-`Experiment` callers compatible.
- Mark the write capability as human/CLI-only and add validation,
  mutation-safety, technique, receipt, and registry coverage.
- Remove experiment construction, restoration, and mutation from Streamlit's
  scientific-memory workflow.

## Deliverables

- Broadened `save_experiment_to_memory` reviewed command.
- Frozen `ScientificMemorySaveReceipt`.
- Streamlit memory-panel migration.

## Success Criteria

Streamlit saves reviewed DLS and chromatography evidence to scientific memory
through application inputs without constructing or mutating `Experiment`
objects.

## Implementation Summary

- Broadened the established reviewed memory command to accept defensively
  copied `Experiment` objects, copied parsed DLS samples, or a
  `ChromatographyAnalysisResult` while retaining injected-store compatibility.
- Added frozen, versioned receipt metadata and explicit empty/malformed input
  validation.
- Kept DLS assembly, chromatography restoration, and reviewed relabeling inside
  the application layer so active analysis evidence is never mutated.
- Migrated both populated and chromatography-only Streamlit memory states to
  submit application inputs while preserving labels, source files, project
  tags, technique tags, notes, explicit confirmation, and success text.
- Restricted the write capability registry entry to Human UI and CLI callers.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/046-promote-reviewed-scientific-memory-save.md`

## Test Results

- Focused memory-command and capability-registry tests: 7 passed.
- Full suite: 218 passed in 2.23s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Migrate the DLS Experiment Brief call so Streamlit submits parsed samples
  without assembling a domain `Experiment` in presentation code.
