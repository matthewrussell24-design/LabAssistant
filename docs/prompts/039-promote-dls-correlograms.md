# Promote DLS Correlograms

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 038 - Promote DLS Raw Evidence

## Objective

Promote DLS correlogram visualization evidence into an immutable application
read while preserving sample order, point order, optional values, noise scores,
empty-state behavior, and hover data.

## Context

Streamlit's secondary correlogram-quality chart still reads measurement traces
and derived noise scores directly from parsed samples.

## Tasks

- Accept parsed DLS samples without a caller-provided DataFrame.
- Preserve ordered non-empty sample series and trace point order.
- Return typed immutable delay, correlation, replicate, and sample-level noise
  evidence without pandas or Plotly details.
- Keep chart construction, labels, hover templates, and empty-state rendering in
  Streamlit.
- Add compatibility, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_correlograms` capability.
- Frozen correlogram point, series, and result read models.
- Streamlit correlogram chart migration.

## Success Criteria

Streamlit renders correlogram diagnostics through one registered application
workflow without reading measurement traces or noise scores directly.

## Implementation Summary

- Added frozen correlogram point, sample-series, and result contracts with
  optional numeric evidence and stable ordering.
- Added and registered `retrieve_dls_correlograms`, omitting samples without
  points while preserving valid all-empty results and sample-level noise scores.
- Routed Streamlit's correlogram-quality chart through immutable series while
  retaining Plotly construction, labels, layout, empty-state text, and hover
  formatting in the shell.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/039-promote-dls-correlograms.md`

## Test Results

- Focused application, multi-file importer, and representative-fixture tests:
  89 passed.
- Full suite: 202 passed in 2.17s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote paired-angle DLS distribution overlay evidence into an immutable
  application read while keeping Plotly and sample selection in Streamlit.
