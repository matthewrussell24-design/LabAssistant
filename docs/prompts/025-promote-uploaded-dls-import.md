# Promote Uploaded DLS Import Preview

Status: Complete
Created: 2026-07-11
Last Updated: 2026-07-11
Priority: High
Depends On: 024 - Promote Experiment Brief Preview

## Objective

Promote Streamlit's uploaded multi-file DLS preview and import orchestration into
a typed immutable application workflow without changing grouping or diagnostics.

## Context

Local-path DLS analysis already crossed the application boundary, but the primary
Streamlit upload path called measurement preview and grouped-import helpers directly.

## Tasks

- Accept generic named readable sources without importing Streamlit types.
- Preserve lot grouping, classified file roles, source text, status, and parser errors.
- Return immutable preview and measurement summaries without pandas tables.
- Provide reviewed copy-on-access parsed samples for the existing workspace.
- Register the workflow and remove direct importer calls from Streamlit.

## Deliverables

- `analyze_dls_uploads` capability.
- Frozen upload-file, group, and import-result read models.
- Streamlit migration and representative compatibility tests.

## Success Criteria

Streamlit imports uploaded DLS evidence through one registered application
capability and no longer imports `build_import_preview` or
`import_measurement_groups`, while existing multi-file grouping and retry behavior remain intact.

## Implementation Summary

- Added immutable `DLSUploadFileRead`, `DLSUploadGroupRead`, and
  `DLSUploadImportResult` contracts.
- Added `analyze_dls_uploads` with generic named/readable source validation,
  unchanged classifier/group importer delegation, resilient import errors, and
  fresh copy-on-access parsed samples.
- Registered the capability for Human UI, CLI, and Future API callers while
  excluding Agent file access.
- Routed Streamlit preview tables, completeness diagnostics, original-source
  display, initial import, and retry through the application result.
- Removed Streamlit's direct measurement-importer dependency.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/025-promote-uploaded-dls-import.md`

## Test Results

- Focused application, multi-file importer, and real-fixture tests: 62 passed.
- Full suite: 175 passed in 2.44s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the remaining DLS-specific decision ranking into an immutable
  application result so Streamlit no longer calls decision-brief helpers directly.
