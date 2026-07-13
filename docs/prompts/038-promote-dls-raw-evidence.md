# Promote DLS Raw Evidence

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 037 - Promote DLS Distribution Series

## Objective

Promote DLS raw-evidence inspection and export into an immutable application
read while preserving point-table columns, metadata order, source diagnostics,
source preview behavior, and CSV output.

## Context

Streamlit's raw-data tabs still read mutable parsed-sample DataFrames, metadata
dictionaries, and source text directly, and independently compose uploaded-file
diagnostics.

## Tasks

- Accept parsed DLS samples and optional immutable upload-group diagnostics.
- Preserve sample order, arbitrary point-table columns and rows, metadata field
  order, original source text, file order, and errors.
- Return typed immutable raw-evidence models without pandas.
- Reconstruct DataFrames, CSV downloads, selection state, and the 12,000-character
  source preview only in Streamlit.
- Add compatibility, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_raw_evidence` capability.
- Frozen raw point-table, metadata, sample, source-file, and result read models.
- Streamlit raw-data panel migration.

## Success Criteria

Streamlit renders and exports raw DLS evidence through one registered
application workflow without reading parsed-sample DataFrames, metadata, or
source text directly.

## Implementation Summary

- Added frozen raw point-table, metadata-field, sample-evidence, source-file,
  and result contracts that preserve arbitrary vendor columns and ordering.
- Added and registered `retrieve_dls_raw_evidence`, composing parsed samples
  with optional upload-group diagnostics without returning pandas.
- Routed Streamlit's point display/download, metadata table, original-file
  diagnostics, and fallback source preview through immutable evidence while
  preserving shell-owned CSV creation, selection, and 12,000-character preview
  truncation.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/038-promote-dls-raw-evidence.md`

## Test Results

- Focused application, view-model, and multi-file importer tests: 81 passed.
- Full suite: 200 passed in 2.31s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote DLS correlogram visualization evidence into an immutable application
  read while keeping Plotly and diagnostic layout in Streamlit.
