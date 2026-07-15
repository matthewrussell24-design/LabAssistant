# 007 - Controlled macOS Python Runtime

Status: Accepted
Date: 2026-07-15
Related Prompt: `docs/prompts/071-select-macos-runtime.md`

## Decision Summary

Qualification builds use the exact arm64 CPython 3.12.13+20260623 stripped
install-only artifact published by Astral's `python-build-standalone` process.
`packaging/macos/runtime.env` pins its HTTPS URL and SHA-256 digest; the build
downloads, verifies, and extracts it outside the repository instead of using a
Python found on `PATH`.

The bundle declares macOS 14.0 as its **qualified binary floor**. This is the
highest deployment target in the complete 76-file Mach-O closure: the runtime
supports 11.0 and NumPy's extensions require 14.0. The inspection script fails
if any native file exceeds the declaration. This is not yet a supported-version
claim by itself; task 072 subsequently passed clean arm64 macOS 14.8.7 and
26.4 execution from the same commit.

## Context and Alternatives

The first bundle inherited a macOS 26 floor from host Homebrew Python. Python
does not publish redistributable macOS CPython archives for this use;
`python-build-standalone` is also the source used by uv for managed Python.
Using the host runtime was rejected as non-reproducible. Building CPython in
place was rejected because it adds an unpinned compiler/SDK pipeline. The older
official installer and a Python-minor upgrade were rejected as stale or outside
the current Python 3.12 lock boundary.

py2app 0.28.10 assumes `zlib` is a loadable extension, while this runtime links
it into the interpreter. The build applies the small, version-bound
`py2app-portable-runtime.patch` after installing the hashed build lock. It also
prefers the controlled runtime's explicit `libpython` before framework-name
lookup, preventing an unrelated host Python framework from entering the bundle.
Remove each patch hunk when an upstream release handles that case.

## Verification and Consequences

- The controlled build, recursive arm64/linkage/signature audit, packaged DLS,
  chromatography, OpenLab, JSONL, SQLite, paths-with-spaces smoke, and Finder
  open/quit pass on the macOS 26.5.2 build host.
- The runtime archive itself contains arm64 Mach-O files with an 11.0 minimum;
  the built bundle contains only 11.0 and 14.0 targets.
- The bundle remains ad-hoc signed, local-only, and non-distributable.
- Runtime and dependency license notices must be assembled and reviewed before
  release; the selected provenance does not waive that release gate.
- A clean-machine matrix must exercise macOS 14 and current macOS, including
  fresh profile, scientific smoke, Finder launch, and upgrade persistence.
  Versions below 14 are unsupported by this dependency closure.

Task 072 satisfied that matrix in hosted run `29447782134`; the reviewed result
is preserved in `docs/status/macos-compatibility-evidence.md`.

## References

- [uv managed Python versions](https://docs.astral.sh/uv/concepts/python-versions/)
- [Astral python-build-standalone](https://github.com/astral-sh/python-build-standalone)
