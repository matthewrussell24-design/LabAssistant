# Stabilize Public Read Contract

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 060 - Review API Schema Freeze

## Objective

Resolve the two remaining freeze blockers by exposing only the seven reviewed
reads and versioning their external envelope independently from application DTOs.

## Tasks

- Define a dedicated public read contract version.
- Project concise public platform/access discovery without changing the 42-entry
  internal application registry.
- Remove internal DTO `api_version` fields from external data payloads.
- Update golden fixtures and repeat the stable freeze review.

## Success Criteria

Discovery exposes exactly seven read-only capabilities, external versioning is
unambiguous, internal callers remain compatible, and the repeated review makes
an explicit stable/no-go transport decision.

## Implementation Summary

- Introduced the independent public read contract version `1.0` while leaving
  internal application DTOs at `0.1-draft`.
- Projected public platform discovery from exactly seven reviewed reads and
  concise access/request metadata.
- Replaced broad agent-policy discovery with accurate local-read-only policy
  metadata.
- Removed internal `api_version` fields recursively from external data payloads.
- Re-ran golden review and promoted the seven-read contract to stable `1.0`.

## Files Changed

- `labassistant/api_readiness.py`
- `tests/test_api_readiness.py`
- `tests/fixtures/api_contract_shape.json`
- `docs/architecture/api-readiness.md`
- `docs/architecture/capabilities.md`
- `docs/decisions/003-api-contract-freeze-policy.md`
- `docs/status/current-state.md`
- `docs/prompts/061-stabilize-public-read-contract.md`

## Test Results

- Focused golden/conformance coverage: 4 passed.
- Full suite: 237 passed in 2.81s.

## Remaining Work

- Select and design the first local read-only transport that maps its trusted
  host identity into the stable access context; no write surface is approved.
