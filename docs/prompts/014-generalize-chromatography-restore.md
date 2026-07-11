# Generalize Persisted Restoration For Chromatography

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 013 - Promote History Overview

## Objective

Add a typed chromatography restoration composition over persisted experiment
history, proving that application-layer restore is not DLS-only.

## Context

Persisted listing and retrieval are shared, but `retrieve_experiment` currently
rehydrates only DLS measurements. Chromatography measurements already serialize
to JSON-compatible dictionaries containing nested peaks and chromatogram traces.

## Tasks

- Reconstruct chromatography measurements, peaks, and traces from history.
- Preserve history provenance without changing the JSONL schema.
- Add immutable chromatography measurement summaries and a versioned result.
- Rebuild deterministic assessment, observations, and hypotheses on restore.
- Test representative restoration, nested evidence, serialization, and errors.

## Deliverables

- `restore_chromatography_experiment` and its typed read models.
- Persistence reconstruction helpers and focused tests.
- Aligned architecture and status documentation.

## Success Criteria

A saved chromatography experiment can be restored through the application
layer into an immutable technique-appropriate read model, while DLS and
malformed records are rejected explicitly.

## Implementation Summary

- Added chromatography-aware history reconstruction for measurements, nested
  peaks, and chromatogram traces with persisted-record provenance.
- Generalized targeted record validation to dispatch by supported measurement
  shape while preserving strict malformed-record errors.
- Added `restore_chromatography_experiment`, which rebuilds deterministic
  assessment, observations, hypotheses, and an immutable versioned read result.
- Preserved the existing JSONL format and DLS retrieval behavior.

## Files Changed

- `labassistant/history.py`
- `labassistant/application.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/014-generalize-chromatography-restore.md`

## Test Results

- Focused application, history, and chromatography tests: 37 passed.
- Full suite: 151 passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Add a representative cross-technique investigation test connecting
  chromatography missing mass, DLS aggregation evidence, and filtration outcomes.
