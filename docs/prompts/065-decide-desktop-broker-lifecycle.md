# Decide Desktop Broker Lifecycle

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 064 - Add Typed Local Read Client

## Objective

Decide whether and how the native desktop may own the local read broker without
hidden startup or coupling scientific reads to window state.

## Tasks

- Compare separate, launch-flag, in-app, automatic, and persistent ownership.
- Define explicit consent, status, collision, thread, and shutdown behavior.
- Define packaging and sandbox constraints.
- Record an implementation sequence and go/no-go gate.

## Success Criteria

An accepted lifecycle decision preserves default-off desktop behavior, gives
opt-in sharing bounded ownership and cleanup, and leaves remote access, writes,
and autonomous behavior excluded.

## Implementation Summary

- Selected a non-persistent `--share-local-reads` desktop launch flag; default
  startup remains listener-free.
- Kept the standalone foreground broker as a supported ownership model.
- Defined owned versus compatible-external collision behavior without adding a
  second stale-socket or unlink policy.
- Required an AppKit-independent worker, cooperative bounded shutdown, outer
  `try/finally`, idempotent cleanup, and safe stderr status.
- Deferred in-app preference persistence and packaged enablement until their
  UI, signing, sandbox, entitlement, and runtime-location gates are known.

## Files Changed

- `docs/decisions/005-desktop-read-broker-lifecycle.md`
- `docs/decisions/README.md`
- `docs/architecture/api-readiness.md`
- `docs/ARCHITECTURE.md`
- `docs/status/current-state.md`
- `docs/prompts/065-decide-desktop-broker-lifecycle.md`

## Test Results

- Markdown links validated across 94 documentation files.
- Full suite: 256 passed in 2.99s.

## Remaining Work

- Implement the bounded opt-in desktop lifecycle owner and cooperative broker
  shutdown described by ADR 005.
