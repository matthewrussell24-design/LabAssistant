# Select Local Read Transport

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 061 - Stabilize Public Read Contract

## Objective

Select the first local read-only transport for the stable `1.0` contract without
implementing a listener.

## Tasks

- Compare in-process calls, Unix-domain IPC, and loopback HTTP for desktop, CLI,
  and future local-agent use.
- Define the threat assumptions and trusted-host identity mapping.
- Define lifecycle, framing, error mapping, and deployment consequences.
- Record an implementation sequence and explicit go/no-go gate.

## Success Criteria

An accepted transport ADR defines a client-neutral local boundary without
opening a listener, adding writes, or treating loopback as authentication.

## Implementation Summary

- Selected owner-only Unix-domain stream IPC with newline-delimited JSON.
- Defined a same-local-OS-user trust model and documented its same-user process
  limitation.
- Required broker-derived peer identity, client identity, origin, and scopes;
  requests cannot assert access context.
- Separated transport framing failures from the unchanged stable application
  envelopes.
- Chose an explicit foreground broker lifecycle and conditional go for a
  minimal adapter after a peer-credential compatibility spike.

## Files Changed

- `docs/decisions/004-local-read-only-transport.md`
- `docs/decisions/README.md`
- `docs/architecture/api-readiness.md`
- `docs/architecture/README.md`
- `docs/ARCHITECTURE.md`
- `docs/status/current-state.md`
- `docs/prompts/062-select-local-read-transport.md`

## Test Results

- Markdown links validated across 90 repository documentation files.
- Full suite: 237 passed in 2.48s.

## Remaining Work

- Implement the bounded foreground Unix-domain read broker after proving peer
  credential retrieval on the supported macOS/Python runtime.
