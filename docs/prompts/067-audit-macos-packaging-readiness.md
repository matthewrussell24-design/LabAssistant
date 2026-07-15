# Audit macOS Packaging Readiness

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 066 - Implement Desktop Broker Lifecycle

## Objective

Audit the native desktop packaging boundary and select the first honest macOS
build, signing, notarization, sandbox, runtime-layout, and distribution target.

## Tasks

- Inventory Python/native dependencies, resources, persistence, IPC, and tools.
- Verify current Apple distribution and sandbox requirements.
- Compare local, Developer ID, Mac App Store, architecture, and packaging tools.
- Define bundle/runtime layout, verification matrix, sequence, and go/no-go.

## Success Criteria

An accepted packaging ADR names one supported first target, prevents mutable
state from entering the bundle, distinguishes local qualification from
distribution, and makes sandbox/universal expansion explicit future work.

## Implementation Summary

- Selected arm64 py2app, Developer ID signing, hardened runtime, notarization,
  direct distribution, and no App Sandbox as the first distribution target.
- Defined an ad-hoc local standalone bundle as a qualification stage only.
- Identified CWD-relative persistence and broad unpinned dependencies as the
  first two repository blockers.
- Defined Application Support/Caches layout, resource boundaries, signing
  rules, sandbox/App Group consequences, and a staged verification matrix.
- Recorded host readiness: arm64 Python 3.12.13, Xcode/notarization tools
  present, py2app absent, and no valid signing identity installed.

## Files Changed

- `docs/decisions/006-macos-packaging-target.md`
- `docs/decisions/README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/status/current-state.md`
- `docs/prompts/067-audit-macos-packaging-readiness.md`

## Test Results

- Markdown links validated across 97 documentation files.
- Full suite: 265 passed in 3.69s.

## Remaining Work

- Centralize packaged runtime paths and define legacy CWD-data migration before
  creating the first local qualification bundle.
