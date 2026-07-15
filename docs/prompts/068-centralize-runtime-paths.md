# Centralize Runtime Paths

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 067 - Audit macOS Packaging Readiness

## Objective

Move mutable default state out of the current working directory through a pure,
platform-aware runtime path contract and explicit safe legacy import.

## Tasks

- Define immutable Application Support and Caches paths without UI dependencies.
- Route lazy history, memory, and socket defaults through the contract.
- Preserve all explicit path injection.
- Add explicit copy-only legacy discovery/migration with no automatic CWD scan.
- Cover fresh, override, legacy, conflict, and unsafe-source behavior.

## Success Criteria

Finder/packaged defaults never depend on CWD, explicit paths remain authoritative,
and legacy data moves only after an explicit safe copy request that leaves the
source untouched.

## Implementation Summary

- Added a pure platform-aware runtime layout with XDG and explicit overrides.
- Routed lazy implicit history, knowledge-store, and socket defaults through it
  while preserving explicit path injection.
- Added an explicit copy-only legacy importer and CLI with owner, file, link,
  conflict, rollback, and source-preservation safeguards.
- Added focused resolution, override, injection, migration, and failure tests.

## Verification

- `scripts/test -q` — 274 passed.

## Remaining Work

Split and reproducibly lock desktop runtime, desktop build, Streamlit, and
development dependencies before adding py2app configuration.
