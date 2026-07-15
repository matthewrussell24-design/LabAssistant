# macOS Compatibility Evidence

Purpose: preserve the reviewed compatibility result after hosted artifacts
expire. Raw logs remain attached to the linked workflow run for 30 days.

## Qualified Matrix

Workflow: [macOS compatibility qualification run 29447782134](https://github.com/matthewrussell24-design/LabAssistant/actions/runs/29447782134)

Commit: `05ed9775a1d0e36c57f2aa79e553906d6384a172`

Controlled runtime SHA-256:
`41df7d3ae4757e84b97874f76d634268456aaa271740d33f968d826374998fb7`

| Row | OS build | Runner image | Native audit | Scientific smoke | Persistence | Finder | Artifact SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Minimum | macOS 14.8.7 (23J520) | `macos14` 20260629.0180.1 | 76 arm64; targets 11.0/14.0 | Passed | 1 → 2 records; SQLite retained | Passed | `d8a0dcb696f14ec9298c0e4d2db97eaca19f5eac0acc0adc824532af4a441baf` |
| Current | macOS 26.4 (25E246) | `macos26` 20260630.0213.1 | 76 arm64; targets 11.0/14.0 | Passed | 1 → 2 records; SQLite retained | Passed | `c8dc6b14fbea644cdfe1c8bb2a43fb0bcf310029ed62b3606a2fdd9196ddc9ee` |

Both summaries reported the same initial SQLite SHA-256,
`6e96041240dac62a277fd57f967c71ba122cb96d0b4c7c48cf7a475fa083189f`.
App sizes differed slightly by build host (155,242,496 and 154,898,432 bytes),
which is recorded but is not a compatibility criterion.

## Interpretation

The controlled arm64 qualification bundle has a qualified macOS 14.0 minimum
for the tested application boundaries. This evidence does not make the ad-hoc
artifact distributable: release identity, third-party notices, Developer ID
signing, hardened runtime, notarization, and Gatekeeper verification remain
separate gates.

The first hosted run (`29447233612`) failed before application execution because
py2app 0.28.10 selected an unrelated host Python framework. Commit `05ed977`
made the controlled runtime library authoritative before framework discovery;
the passing matrix demonstrates that the correction removed host contamination.
