# Run Clean macOS Compatibility Matrix

Status: In Progress — automation complete; external rows pending
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 071 - Select macOS Bundle Runtime and Compatibility Floor

## Objective

Execute and archive the controlled qualification bundle on fresh arm64 macOS
14 and current-macOS machines before converting the candidate binary floor into
a supported-version claim.

## Tasks

- Run the same checksum-pinned build and native audit on both OS versions.
- Exercise scientific/runtime behavior with a fresh profile.
- Reuse persisted history and SQLite state across consecutive app executions.
- Exercise Finder launch and graceful termination.
- Archive OS, runner-image, commit, runtime-digest, size, and persistence evidence.
- Keep signing, notarization, sandbox, universal2, and release publication out of scope.

## Implementation Record

`scripts/qualify-macos-compatibility` now owns the common evidence-producing
sequence. `.github/workflows/macos-compatibility.yml` selects explicit fresh
arm64 `macos-14` and `macos-26` hosted runners and archives each row's log and
summary. GitHub documents each standard hosted job as a newly provisioned VM.

The workflow has not run because this task is committed locally and repository
policy prohibits pushing without explicit user authorization. Consequently the
macOS 14 floor remains a candidate and neither clean row is marked passed.

The common runner passed locally on arm64 macOS 26.5.2 (build 25F84): 76 native
files passed the 11.0/14.0 target audit, scientific smoke passed, persistence
reuse grew history from one to two records while retaining SQLite state, and
Finder open/quit passed. This validates the harness but is not a clean hosted
matrix row.

The first hosted run (`29447233612`) failed during py2app's build on both rows.
The controlled prefix is named `python`; py2app 0.28.10 performed a framework
name lookup first and selected each runner's unrelated system Python framework,
including Python 3.11 and Tcl. Signing then failed on that contaminated payload.
The portable-runtime patch now returns the controlled prefix's explicit
`libpython3.12.dylib` before framework lookup. The corrected bundle and all
smokes pass locally; a second hosted run is pending. The workflow also uses the
current Node 24 checkout/artifact actions to avoid deprecated action runtimes.

## Success Criteria

Both hosted rows pass from the same commit and their evidence artifacts are
reviewed. Any failure changes the floor or implementation before a compatibility
claim is made. A local build-host pass alone cannot complete this task.
