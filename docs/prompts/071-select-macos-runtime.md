# Select macOS Bundle Runtime and Compatibility Floor

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 070 - Qualify Standalone py2app Bundle

## Objective

Replace the host-bound Homebrew Python with a reproducible arm64 CPython runtime,
derive an honest deployment target from every bundled Mach-O, and define the
remaining clean-machine matrix.

## Tasks

- Compare controlled Python 3.12 runtime sources and document provenance/licensing.
- Pin the selected artifact URL, build identifier, and SHA-256 digest.
- Build and smoke the standalone bundle with that runtime rather than PATH Python.
- Require every bundled Mach-O to be arm64 and at or below the declared floor.
- Record which compatibility claims require clean external machines.

## Success Criteria

The repository reproducibly acquires and verifies one controlled runtime, the
bundle passes existing audits without host Python linkage, and its declared
minimum follows the inspected binary closure. Compatibility is claimed only for
macOS versions actually exercised on clean arm64 machines.

## Completion Record

Selected and checksum-pinned Astral `python-build-standalone` CPython
3.12.13+20260623 for arm64. The build now ignores host Python, verifies the
runtime archive, applies a bounded py2app built-in-zlib compatibility patch,
and declares macOS 14.0 from the inspected native closure. The rebuilt bundle
contains 76 arm64 Mach-O files with only 11.0 and 14.0 deployment targets; its
structural audit, packaged scientific/runtime smoke, and Finder open/quit pass
on macOS 26.5.2. Clean macOS 14 and current-macOS validation remains the next
gate, so 14.0 is a candidate binary floor rather than a support claim.
