# Promote DLS Filtration Evidence

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 043 - Promote DLS Circulation Time

## Objective

Promote reviewed filtration retrieval, set/clear, and CSV batch attachment
behind parsed-sample application contracts while preserving filtration fields,
pressure normalization, sample-name matching, overwrite and clear semantics,
unmatched ordering, session prefill, and explicit user actions.

## Context

Streamlit still reads and mutates filtration provenance directly on parsed DLS
measurements for manual entry, CSV attachment, and current-evidence display.

## Tasks

- Reuse the immutable filtration summary rather than duplicate its field schema.
- Add a versioned parsed-sample filtration read.
- Add reviewed set/clear and ordered batch-attachment commands.
- Preserve existing domain mutation, sample matching, overwrite, clear, and
  malformed-provenance behavior.
- Keep pressure normalization, widgets, session keys/prefill, explicit buttons,
  and display formatting in Streamlit.
- Register reads for human/CLI/future API callers and mutations for human/CLI
  callers only.
- Add compatibility, validation, immutability, matching, and registry coverage.

## Deliverables

- `retrieve_dls_filtration_measurement` capability.
- `set_dls_filtration_measurement` reviewed command.
- `attach_dls_filtration_measurements` reviewed batch command.
- Frozen single-sample and attachment result models.
- Streamlit manual, CSV, and attached-evidence migration.

## Success Criteria

Streamlit retrieves and attaches reviewed filtration evidence through
parsed-sample application contracts without direct measurement access.

## Implementation Summary

- Reused the immutable filtration summary inside a versioned parsed-sample read
  rather than duplicating the field schema.
- Added and registered single-sample retrieval, reviewed set/clear, and ordered
  exact-name batch attachment with immutable matched/unmatched results.
- Migrated manual session application, manual prefill, CSV attachment, and the
  current-evidence table while retaining widgets, pressure normalization,
  explicit buttons, session updates, and formatting in Streamlit.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/044-promote-dls-filtration-evidence.md`

## Test Results

- Focused application, trend-analysis, and filtration tests: 101 passed.
- Full suite: 212 passed in 2.47s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Migrate the saved DLS workspace loader to the technique-aware restore workflow
  without reconstructing parsed samples in Streamlit.
