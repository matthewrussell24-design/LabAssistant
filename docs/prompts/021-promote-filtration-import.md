# Promote Filtration CSV Import

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 020 - Promote Chromatography And OpenLab Analysis

## Objective

Move filtration CSV parsing and preview summaries behind a typed immutable
application workflow while preserving explicit user-reviewed attachment to DLS samples.

## Tasks

- Preserve column diagnostics, row warnings, validation errors, and source provenance.
- Return immutable measurement and trace summaries with normalized units.
- Avoid exposing the mutable importer result or pandas table.
- Provide copy-on-access measurements only for the explicit attach action.
- Register the workflow without Agent file access and migrate Streamlit.

## Success Criteria

Streamlit renders filtration CSV diagnostics and summaries through the
application layer, then attaches fresh measurements only after the existing
explicit button confirmation.

## Implementation Summary

- Added frozen filtration measurement, trace, and import-result read models.
- Added and registered `analyze_filtration_csv`, preserving column diagnostics,
  row warnings, errors, normalized time/pressure values, and source provenance.
- Added copy-on-access measurement restoration while keeping exact DLS sample
  matching and attachment behind the existing explicit Streamlit button.
- Removed Streamlit's direct filtration importer and mutable-result dependency.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/021-promote-filtration-import.md`

## Test Results

- Focused application, filtration, and trend tests: 55 passed.
- Full suite: 166 passed in 2.11s.
- Headless Streamlit startup smoke passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote the explicit persisted-experiment save into a validated application
  command so Streamlit no longer writes JSONL history directly.
