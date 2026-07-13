# Promote DLS Circulation Time

Status: Complete
Created: 2026-07-13
Last Updated: 2026-07-13
Priority: High
Depends On: 042 - Promote DLS History Save Inputs

## Objective

Promote reviewed DLS circulation-time attachment and retrieval behind
parsed-sample application contracts while preserving supported units, minute
normalization, overwrite and clear semantics, missing values, source
provenance, session-prefill behavior, and explicit user entry.

## Context

Streamlit still reads and mutates circulation-time provenance directly on each
parsed sample's measurement, even though downstream trend analysis already
crosses an immutable application contract.

## Tasks

- Add a frozen, versioned circulation-time read contract.
- Add parsed-sample retrieval and reviewed mutation entry points.
- Preserve the established domain helper's unit validation, normalization,
  overwrite, clear, malformed-provenance, and source behavior.
- Keep session keys, input parsing, widgets, and the decision not to write blank
  values in Streamlit.
- Register the read for human/CLI/future API callers and the reviewed mutation
  for human/CLI callers only.
- Add compatibility, validation, immutability, and registry coverage.

## Deliverables

- `retrieve_dls_circulation_time` capability.
- `set_dls_circulation_time` reviewed command.
- Frozen `DLSCirculationTimeRead` model.
- Streamlit circulation-time migration.

## Success Criteria

Streamlit passes parsed samples and reviewed time values through explicit
application contracts without directly accessing measurement provenance.

## Implementation Summary

- Added a frozen circulation-time read with entered value, original unit,
  normalized minutes, source, sample identity, and API version.
- Added and registered parsed-sample retrieval plus a reviewed human/CLI-only
  set/clear command backed by the established trend-domain helpers.
- Migrated Streamlit's session application and widget prefill without moving
  session keys, parsing, supported-unit choices, or blank-write decisions out of
  the shell.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/043-promote-dls-circulation-time.md`

## Test Results

- Focused application and trend-analysis tests: 92 passed.
- Full suite: 209 passed in 2.65s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote reviewed filtration attachment and retrieval behind parsed-sample
  application contracts while preserving explicit manual and CSV workflows.
