# Promote DLS History Inputs

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 040 - Promote DLS Paired-Angle Overlays

## Objective

Move the DLS history panel's comparison and similar-run inputs behind
parsed-sample application workflows while preserving existing measurement
callers, baseline selection, sample order, drift labels, similarity ranking,
empty states, and display formatting.

## Context

The history results already cross immutable application contracts, but
Streamlit still unwraps mutable `Measurement` objects from parsed samples before
calling those capabilities.

## Tasks

- Extend the established comparison and related-run capabilities to accept
  parsed DLS samples without duplicating capability names.
- Retain compatibility for existing `Measurement` callers.
- Keep baseline choice, sample choice, pandas formatting, and session state in
  Streamlit.
- Add parsed-sample compatibility and invalid-input coverage.
- Remove direct measurement extraction from the two history-panel reads.

## Deliverables

- Parsed-sample inputs for `compare_experiments` and
  `find_related_experiments`.
- Streamlit history-panel migration.
- Updated architecture and handoff documentation.

## Success Criteria

Streamlit requests immutable comparison and related-run results from parsed DLS
samples without directly extracting their measurement models.

## Implementation Summary

- Added one internal input resolver shared by the established comparison and
  related-run capabilities.
- Accepted parsed DLS samples while preserving existing `Measurement` callers,
  baseline behavior, result order, drift labels, ranking, and empty results.
- Migrated Streamlit's history comparison and selected-sample similarity call
  without moving selection or DataFrame formatting out of the shell.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/041-promote-dls-history-inputs.md`

## Test Results

- Focused application and history tests: 87 passed.
- Full suite: 206 passed in 2.52s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Let the experiment-history save command accept parsed DLS samples directly
  while preserving explicit append-only semantics and defensive copying.
