# Add Typed Local Read Client

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 063 - Implement Local Read Broker

## Objective

Add a typed, immutable Python client over the stable local read broker without
adding automatic broker startup, an autonomous agent runtime, or writes.

## Tasks

- Define typed success payloads and capability-specific read methods.
- Keep connection, transport, protocol, and stable application errors distinct.
- Validate transport/request correlation and stable contract version.
- Prove compatibility with all seven broker reads.

## Success Criteria

Callers use typed immutable results instead of parsing raw envelopes, all seven
reads retain their stable semantics, and failures preserve the layer that
produced them.

## Implementation Summary

- Added one capability-specific method for each stable read and immutable typed
  payload/result dataclasses.
- Recursively froze open-ended nested scientific records rather than duplicating
  application domain models.
- Added distinct connection, transport, protocol, and stable application error
  types with safe messages and preserved error metadata.
- Validated request correlation, transport and contract versions, capability,
  envelope status, and required response fields.
- Exported the client and error surface from the top-level package without
  starting or managing the broker.

## Files Changed

- `labassistant/local_read_client.py`
- `labassistant/__init__.py`
- `tests/test_local_read_client.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/architecture/api-readiness.md`
- `docs/status/current-state.md`
- `docs/prompts/064-add-typed-local-read-client.md`

## Test Results

- Focused client/transport/API tests: 23 passed in 0.34s.
- Full suite: 256 passed in 2.51s.
- Markdown links validated across 92 documentation files.
- Independent-process smoke: typed discovery returned seven capabilities and
  typed protected experiment listing succeeded; broker shutdown cleaned up.

## Remaining Work

- Decide whether and how the native desktop should explicitly opt into owning
  the broker lifecycle; do not add hidden automatic startup.
