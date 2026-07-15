# Qualify Standalone py2app Bundle

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 069 - Split and Lock Dependency Groups

## Objective

Build and inspect the first standalone arm64 py2app artifact for the native
desktop as an explicitly non-release, local qualification bundle.

## Tasks

- Add minimal py2app metadata with a visibly non-release bundle identity.
- Build without alias mode from the hash-locked build dependency group.
- Add repeatable bundle inspection and packaged scientific-runtime smoke checks.
- Verify native architecture/linkage, dependency exclusions, runtime paths,
  default-off IPC, DLS/XLSX, chromatography CSV, history, and SQLite memory.
- Record honest remaining signing, deployment-target, compatibility, and GUI gates.

## Success Criteria

The standalone arm64 bundle launches independently of the repository virtual
environment, passes the bounded packaged smoke and structural audit, writes
only to explicit approved runtime locations, and cannot be mistaken for a
signed, notarized, sandboxed, universal, or distributable release.

## Implementation Summary

- Added a local-only py2app entry/configuration and clean hash-locked build.
- Added explicit hidden-import handling and post-build arm64 thinning.
- Added repeatable identity, exclusion, architecture, linkage, signature, and
  packaged runtime/science audits.
- Confirmed real Launch Services open/quit and removed the build environment
  before executing the standalone artifact.

## Files Changed

- `packaging/macos/LabAssistantQualification.py` and `setup.py`
- `labassistant/packaging_smoke.py`
- `scripts/build-macos-qualification`, `inspect-macos-qualification`, and
  `smoke-macos-qualification`
- `tests/test_packaging_smoke.py`
- `.gitignore`, README, architecture, ADR 006, and project status

## Test Results

- Bundle audit: 135 thin arm64 Mach-O files; exclusions/linkage/signature passed.
- Packaged smoke: DLS/XLSX, chromatography CSV, OpenLab `.olax`, history,
  SQLite, paths with spaces, and default-off socket passed.
- Launch Services open and clean quit passed.
- `scripts/test -q` — 278 passed after one isolated Research Journal ordering
  rerun; the first full run had one nondeterministic same-second ordering failure.

## Remaining Work

The bundled Homebrew Python and native support files declare macOS 26.0, while
other embedded files declare 11.0 and 14.0. Select a controlled Python runtime,
freeze the actual deployment target, and validate clean arm64 machines before
any signing or distribution work.
