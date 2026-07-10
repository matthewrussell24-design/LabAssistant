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

Use PySide6 for this prototype. It provides a native macOS Qt window and file
dialog, works with the repository's verified Homebrew Python 3.12 environment,
and has a credible path to future packaging. The tradeoff is a large dependency
compared with Tkinter. Tkinter was initially preferred for minimalism, but the
pre-implementation runtime check found that the project interpreter lacks
`_tkinter`; relying on the unrelated system Python would make the documented
launcher unreliable. PySide6 is therefore the smallest dependable choice for
the repository as configured.

This is a prototype-shell decision, not a permanent desktop-framework lock-in:
the application contracts must remain toolkit-independent.

## Scope

- Add one application capability that accepts existing supported local DLS
  files, performs grouping/import/analysis, and returns a concise typed result.
- Add a small PySide6 shell that selects one or more files and renders the
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
- Added a minimal PySide6 shell with a native file dialog and compact text
  summary; it imports only application contracts and contains no scientific
  calculations.
- Added `scripts/run-desktop` while retaining `scripts/run` for Streamlit.
- Added focused application-contract and display-format tests using the
  representative DLS workbook dataset.

## Test Results

- Focused application, desktop, multi-file, and real-fixture tests: 27 passed.
- Full suite: 132 passed in 2.18s.
- Streamlit headless startup: successful on port 8765.
- Native PySide6 window launch: successful with the project `.venv`.
