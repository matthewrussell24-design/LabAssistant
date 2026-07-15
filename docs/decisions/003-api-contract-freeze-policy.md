# 003 - API Contract Freeze Policy

Status: Accepted
Date: 2026-07-15
Related Prompt: `docs/prompts/057-audit-api-readiness.md`

## Context

The application registry contains 42 useful in-process capabilities. Their
shared `0.1-draft` label and `Future API` caller metadata do not make their
Python signatures safe external contracts. Several accept mutable domain
objects, workspace adapters, local paths, stores, or file-like objects; writes
also require human review.

## Decision

- Registry names remain stable application intent, not automatic endpoints.
- External responses use a common versioned success or error envelope.
- Draft schemas may change with prompt, tests, and handoff documentation.
- A stable schema uses `MAJOR.MINOR`: additive optional fields increment MINOR;
  removals, renames, semantic changes, required fields, and type changes
  increment MAJOR.
- Error codes and meaning are part of the schema contract.
- External requests never select filesystem paths, persistence stores, or
  in-process domain collaborators directly.
- Reads containing scientific history or memory require an explicit access
  boundary. Writes require authorization, confirmation, idempotency, and audit.
- The first freeze is limited to the seven candidates documented in
  `docs/architecture/api-readiness.md`.

## Consequences

- No HTTP framework or agent SDK is selected by this decision.
- Existing in-process callers remain compatible.
- `0.1-draft` remains honest until envelope and conformance work is complete.
- New registry entries must be classified before being proposed externally.
