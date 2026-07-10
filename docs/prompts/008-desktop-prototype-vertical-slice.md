# Desktop Prototype Vertical Slice

Status: Complete
Created: 2026-07-10
Priority: High
Depends On: 007 - Expand DLS Format Regression Coverage

## Objective

Prove that LabAssistant can run as a native macOS desktop application without
depending on Streamlit, while preserving the existing Streamlit shell as a
compatible interface over the same scientific core.

## Framework Recommendation

Use PyObjC with AppKit and WebKit for this macOS prototype. AppKit provides the
real native window and file panel; an embedded local WebKit view provides the
polished card-based workspace without a server. The tradeoff is macOS-only UI
code, which is appropriate for the current target but would require a separate
shell on other platforms. Tkinter was unavailable in the project interpreter,
and repeated PySide6 versions proved nondeterministic because their installed
Cocoa platform plugin could fail between fresh login-shell launches.

This is a prototype-shell decision, not a permanent desktop-framework lock-in:
the application contracts must remain toolkit-independent.

## Scope

- Add one application capability that accepts existing supported local DLS
  files, performs grouping/import/analysis, and returns a concise typed result.
- Add a small AppKit/WebKit shell that selects one or more files and renders the
  experiment identity, evidence count, observation count, and key per-lot DLS
  results.
- Add a local launcher and launch documentation.
- Preserve `app.py` and the existing Streamlit launcher.
- Add application and desktop presentation tests without requiring a GUI
  display in the test environment.

## Non-Goals

- Authentication, HTTP APIs, agents, new instruments, packaging/notarization,
  persistence redesign, and extensive visual design.
- Importing or reusing functions from `app.py`.
- Duplicating parsing, scientific metrics, observation generation, or
  experiment assembly in the desktop module.

## Success Criteria

On macOS, `scripts/run-desktop` opens a native window, the user can choose a
supported DLS dataset, existing application contracts perform the analysis,
and the window displays a concise result summary. Streamlit remains operational
through `scripts/run`, and the full test suite passes.

## Implementation Summary

- Added `analyze_dls_dataset`, a typed application capability that owns local
  file validation, multi-file grouping, DLS measurement assembly, observation
  generation, experiment snapshotting, and concise per-lot result projection.
- Added a minimal native shell with an AppKit file dialog and compact WebKit
  summary; it imports only application contracts and contains no scientific
  calculations.
- Reconciled launch hardening: the launcher accepts optional paths for
  deterministic smoke testing, verifies the pinned PyObjC runtime, and rejects
  unrelated files instead of creating empty measurements. The final AppKit
  implementation removes Qt's unreliable platform-plugin layer entirely.
- Added `scripts/run-desktop` while retaining `scripts/run` for Streamlit.
- Added focused application-contract and display-format tests using the
  representative DLS workbook dataset.

## Test Results

- Focused application, desktop, multi-file, and real-fixture tests: 27 passed.
- Full suite: 133 passed in 2.53s.
- Streamlit headless startup: successful on port 8765.
- Native AppKit window launch: successful with the project `.venv`; the
  representative three-file DLS dataset rendered one Lot 1 measurement with
  Z-average 359 nm, PDI 0.323, primary peak/D50 267 nm, high aggregation risk,
  quality score 43.4, and the dual-angle warning.
