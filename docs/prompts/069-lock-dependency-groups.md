# Split and Lock Dependency Groups

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 068 - Centralize Runtime Paths

## Objective

Separate native desktop, Streamlit, packaging-build, and development inputs and
produce reproducible Python 3.12 macOS arm64 locks with integrity hashes.

## Tasks

- Inventory direct runtime imports by application surface.
- Add small human-maintained input groups without duplicating shared science dependencies.
- Generate wheel-only macOS arm64 locks with hashes through a repository script.
- Preserve `pip install -r requirements.txt` as the full contributor setup.
- Verify isolated group installation, imports, and the complete test suite.

## Success Criteria

Each application surface has an explicit install boundary, generated locks are
reviewable and reproducible, native desktop inputs exclude Streamlit and test
tools, and a clean Python 3.12 environment can install and exercise each group.

## Implementation Summary

- Split direct dependencies into shared runtime, native desktop, Streamlit,
  py2app build, and complete development inputs.
- Generated four wheel-only Python 3.12 macOS arm64 locks with SHA-256 hashes.
- Preserved `requirements.txt` as the complete contributor compatibility entry.
- Added boundary tests and documented installation and deterministic regeneration.

## Files Changed

- `requirements.txt`
- `requirements/*.in`, `requirements/locks/*.txt`, and `requirements/README.md`
- `scripts/lock-dependencies`
- `tests/test_dependency_locks.py`
- Packaging ADR, README, and project status

## Test Results

- Four clean Python 3.12 environments installed with `--require-hashes` and
  passed group-specific import checks.
- A fifth clean environment installed successfully through the compatibility
  `pip install -r requirements.txt` entry point.
- A second lock generation produced byte-identical outputs.
- `scripts/test -q` — 277 passed.

## Remaining Work

Add the minimal non-release py2app configuration and qualify a standalone arm64
bundle without alias mode, signing, notarization, or release claims.
