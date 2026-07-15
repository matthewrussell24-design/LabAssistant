# Stabilize The DLS Evidence Input Contract

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 049 - Audit The Streamlit Application Boundary

## Objective

Define a presentation-neutral DLS sample evidence contract and migrate
application and scientific-core entry points away from direct
`labassistant.view_models` coupling without changing current shell behavior.

## Context

Task 049 completed extraction of current human workflows but found that
`labassistant.application` still imported DLS helpers from the Streamlit-shaped
view-model module. Existing callers already use a structural sample shape, and
Streamlit needs its mutable pandas-backed workspace objects to remain compatible.

## Tasks

- Add a named structural DLS evidence protocol outside the presentation layer.
- Provide a local workspace implementation and measurement conversion adapter.
- Preserve `ParsedSample` and existing view-model helper imports through a
  compatibility facade.
- Migrate application, interpretation, observation, and trend modules away from
  importing `labassistant.view_models`.
- Add tests for structural conformance, compatibility identity, and unchanged
  application behavior.

## Deliverables

- `DLSSampleEvidence` protocol and `DLSWorkspaceEvidence` adapter.
- Backwards-compatible `labassistant.view_models` facade.
- Application/scientific-core imports routed through the neutral evidence module.

## Success Criteria

No reusable application or scientific-core module imports
`labassistant.view_models`, established `ParsedSample` callers remain compatible,
and the full suite preserves existing scientific outputs.

## Implementation Summary

- Added the runtime-checkable `DLSSampleEvidence` structural protocol without a
  Streamlit dependency and a mutable `DLSWorkspaceEvidence` implementation for
  current local workspace behavior.
- Moved parsed-upload conversion, Measurement conversion, status, metrics-table,
  and angle-table helpers into `labassistant.dls_evidence`.
- Replaced `labassistant.view_models` with a compatibility facade that preserves
  `ParsedSample` as an identity alias and re-exports all established helpers.
- Migrated application, interpretation, observation, and trend modules away
  from importing the presentation facade and annotated DLS application entry
  points with the neutral protocol.
- Exported the new contract and adapter from the package root.

## Files Changed

- `labassistant/dls_evidence.py`
- `labassistant/view_models.py`
- `labassistant/application.py`
- `labassistant/interpretation.py`
- `labassistant/observations.py`
- `labassistant/trend_analysis.py`
- `labassistant/__init__.py`
- `tests/test_view_models.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/050-stabilize-dls-evidence-input.md`

## Test Results

- Focused application, view-model, interpretation, observation, and trend suite:
  112 passed in 2.30s.
- Full suite: 225 passed in 2.60s.
- Python compile verification and `git diff --check` passed.
- Headless Streamlit startup and health smoke passed on port 8765.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Migrate DLS metrics/status projection from the workspace metrics dictionary to
  authoritative `Measurement` evidence, keeping the workspace contract as a
  compatibility adapter and pandas out of application read outputs.
