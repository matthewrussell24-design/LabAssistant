# Promote DLS Paired-Angle Overlays

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 039 - Promote DLS Correlograms

## Objective

Promote paired-angle DLS distribution-overlay evidence into an immutable
application read while preserving sample order, forward/back identification,
point order, normalized intensity, missing-curve behavior, and chart labels.

## Context

Streamlit's dual-angle comparison still reads forward and backscatter
distributions directly from mutable parsed measurements.

## Tasks

- Accept parsed DLS samples without caller-provided presentation objects.
- Preserve every sample and its ordered forward/back curve evidence.
- Return typed immutable diameter and normalized-intensity points without
  pandas or Plotly details.
- Keep sample selection, fixed angle labels, colors, hover templates, and
  missing-curve rendering in Streamlit.
- Add compatibility, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_paired_angle_overlays` capability.
- Frozen paired-angle point, curve, sample, and result read models.
- Streamlit paired-angle overlay migration.

## Success Criteria

Streamlit renders paired-angle distribution evidence through one registered
application workflow without reading measurement distributions directly.

## Implementation Summary

- Added frozen point, curve, sample, and result contracts with stable sample,
  curve, and measurement-point ordering.
- Added and registered `retrieve_dls_paired_angle_overlays`, retaining samples
  with missing or empty curves so callers can preserve the established empty
  state.
- Routed Streamlit's paired-angle chart through immutable evidence while
  retaining selection, fixed angle labels, colors, hover formatting, and Plotly
  composition in the shell.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/040-promote-dls-paired-angle-overlays.md`

## Test Results

- Focused application, aggregation, and representative-fixture tests: 95
  passed.
- Full suite: 204 passed in 2.33s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote the DLS history panel's comparison and similar-run inputs behind
  parsed-sample application workflows.
