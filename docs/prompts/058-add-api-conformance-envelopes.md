# Add API Conformance Envelopes

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 057 - Audit API Readiness

## Objective

Add a transport-neutral invocation and serialization boundary for the seven
candidate reads without changing their existing Python handlers or adding a
server.

## Tasks

- Define immutable success and error envelopes with stable draft codes.
- Add a versioned experiment-list result.
- Whitelist candidate names and request parameters.
- Prevent request-controlled path/store collaborator injection.
- Require a trusted access decision for scientific history and memory reads.
- Add deterministic JSON conformance and error-mapping coverage.

## Success Criteria

All seven candidates produce JSON-safe success/error shapes, current handlers
remain backward compatible, unsupported parameters cannot reach local stores,
and transport selection remains deferred.

## Implementation Summary

- Added immutable draft success/error envelopes and the six-code error catalog.
- Added `ExperimentListings` so the existing tuple handler remains compatible
  while external serialization gains a versioned result.
- Added a seven-name invocation whitelist with per-capability parameter schemas.
- Rejected request-controlled path/store collaborators before handler calls.
- Required a trusted adapter access decision for scientific history/memory.
- Mapped not-found, invalid, unsupported, denied, and internal failures without
  exposing unexpected exception text.

## Files Changed

- `labassistant/api_readiness.py`
- `tests/test_api_readiness.py`
- `docs/architecture/api-readiness.md`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/058-add-api-conformance-envelopes.md`

## Test Results

- Focused API conformance coverage: 4 passed.
- Full suite: 237 passed in 2.45s.

## Remaining Work

- Define the trusted local read-access policy and add bounded pagination/limits
  to history, context, and journal candidates before replacing `0.1-draft`.
