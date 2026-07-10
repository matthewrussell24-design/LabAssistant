# Define the LabAssistant Capability Layer

Status: Complete
Created: 2026-07-10
Completed: 2026-07-10
Priority: High
Depends On: 003 - Refine the Living Project Status Document

## Objective

Define the stable, transport-independent capability layer that represents what
LabAssistant can do before introducing an HTTP API, Agent SDK, or additional UI
refactors.

## Tasks

- Audit the application boundary and Streamlit-owned workflows.
- Define capability inputs, outputs, expected errors, and caller types.
- Add a lightweight registry for implemented application operations.
- Preserve public imports and avoid network or persistence changes.
- Add focused contract tests and update project documentation.

## Deliverables

- Capability architecture document and audit.
- Immutable in-process capability registry.
- Focused registry compatibility tests.
- Updated architecture index and living status.

## Success Criteria

Developers can understand LabAssistant's implemented and candidate scientific
workflows without reading their implementation. Future interfaces have stable
capability names and direct, backwards-compatible Python entry points.

## Implementation Summary

- Documented six existing capabilities and ten candidate boundaries.
- Added immutable `CapabilityContract` metadata with `list_capabilities()` and
  `get_capability()` discovery functions.
- Published handler-free capability metadata through the existing app manifest.
- Kept existing handlers and imports intact; no dispatcher or transport was
  introduced.
- Documented transitional domain-model exposure, current error behavior,
  Streamlit-owned workflows, and the recommended retrieval capability.

## Files Changed

- `labassistant/application.py`
- `labassistant/__init__.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/architecture/README.md`
- `docs/prompts/004-define-capability-layer.md`
- `docs/status/current-state.md`

## Test Results

- Focused application tests: 8 passed.
- Full suite: 121 passed in 3.41s.

## Remaining Work

- Promote candidate capabilities only when an existing human workflow can use
  them.
- Start with persisted experiment retrieval through the current Streamlit
  saved-experiment workflow.
