# Promote DLS Distribution Series

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 036 - Promote DLS Metrics Projection

## Objective

Promote DLS distribution-series visualization evidence into immutable
application rows while preserving signal availability, point filtering, sample
order, normalization, reference deltas, and peak annotations.

## Context

Streamlit still reads parsed-sample DataFrames and distribution-column metadata
directly to build signal choices, overlays, delta charts, and small multiples.

## Tasks

- Accept parsed DLS samples without a caller-provided DataFrame.
- Preserve intensity, volume, and number signal identification separately from
  usable-point availability.
- Return ordered typed immutable series, points, and local peaks without pandas.
- Keep normalization, nearest-diameter reference deltas, Plotly construction,
  and UI state in Streamlit.
- Add compatibility, ordering, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_distributions` capability.
- Frozen DLS distribution projection, series, point, and peak read models.
- Streamlit migration for signal selection and all distribution visualizations.

## Success Criteria

Streamlit obtains typed distribution evidence through one registered
application workflow, no visualization reads parsed-sample DataFrames directly,
and existing overlay, delta, normalization, and peak behavior remains stable.

## Implementation Summary

- Added frozen distribution projection, sample, series, point, and peak read
  models with explicit source-column identification and stable ordering.
- Added and registered `retrieve_dls_distributions`, preserving signal choices,
  positive-diameter/nonnegative-signal filtering, raw local peaks, statuses, and
  the intensity fallback without returning pandas.
- Routed Streamlit's signal selector, overlay, delta chart, and small multiples
  through immutable evidence while retaining normalization, nearest-diameter
  alignment, Plotly construction, and interaction state in the shell.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/037-promote-dls-distribution-series.md`

## Test Results

- Focused application, view-model, metrics, and multi-file importer tests: 90
  passed.
- Full suite: 198 passed in 2.51s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote DLS raw evidence inspection and export into an immutable application
  read while preserving original source diagnostics and shell-owned rendering.
