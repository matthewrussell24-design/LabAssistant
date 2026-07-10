# Promote Persisted Experiment Listing Into The Application Layer

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 005 - Promote Persisted Experiment Retrieval, 009 - Polish Desktop Research Workspace

## Objective

Add a versioned, read-only application query for browsing persisted experiment
history and use it to populate the desktop History timeline and enable the
"Open Existing Experiment" action. Restoring a selected record must go through
the existing `retrieve_experiment` capability. Scientific calculations, domain
models, and the Streamlit workflow remain unchanged.

## Context

Task 009 delivered a polished desktop research workspace but honestly disabled
persisted history and the "Open Existing Experiment" action because no
desktop-safe list/restore application contract existed. Session history was the
only timeline. `retrieve_experiment` (task 005) already loads one record safely,
but nothing lets a shell enumerate saved records without reading JSONL storage
directly, which the architecture forbids for interface shells.

## Tasks

- Add `list_experiments` returning immutable, metadata-only listings ordered
  newest-first, tolerant of malformed JSONL lines.
- Add an `ExperimentListing` read model that never exposes mutable measurements.
- Register `list_experiments` in the capability catalog.
- Add `restore_dls_experiment`, composing `retrieve_experiment` and the shared
  DLS summary assembly so a saved record renders through the same read model as
  a freshly imported dataset.
- Populate the desktop History timeline with persisted records on launch and
  restore a selected record on click.
- Enable "Open Existing Experiment" only when persisted history exists.

## Deliverables

- `labassistant/application.py`: `ExperimentListing`, `list_experiments`,
  `restore_dls_experiment`, shared `_dls_measurement_summaries` helper, and the
  new capability registration.
- `labassistant/ui/presenters.py`: `persisted_history_payload` metadata
  serializer with a readable saved-time.
- `labassistant/ui/web_workspace.py`: persisted history section, enabled
  "Open Existing Experiment" action, and restore message hooks.
- `labassistant/ui/macos_window.py`: startup history load and restore handler.
- Tests and documentation updates.

## Success Criteria

The desktop timeline lists persisted experiments through a versioned application
query and restores a selected record through the existing retrieval capability,
without exposing mutable measurements through the listing or letting the UI read
JSONL storage directly. The Streamlit workflow and all prior tests still pass.

## Implementation Summary

- Added `list_experiments(*, history_path=...)`, returning a tuple of frozen
  `ExperimentListing` records (record id, saved time, label, measurement count,
  api version). Ordering matches `latest_experiment`: newest `saved_at` first
  with append order breaking same-second ties. Malformed JSONL lines are skipped
  by the existing tolerant reader so one damaged record cannot hide the timeline.
- Added `restore_dls_experiment(record_id, *, history_path=...)`, which calls
  `retrieve_experiment`, rebuilds samples, and returns a `DLSAnalysisResult`
  identical in shape to `analyze_dls_dataset`. Extracted the per-lot summary
  block into `_dls_measurement_summaries` so import and restore share it.
- Registered `list_experiments` between `import_chromatography_experiment` and
  `retrieve_experiment` in the capability catalog.
- Added `persisted_history_payload` (metadata plus a compact `saved_display`).
- The desktop workspace now renders a "This Session" and a "Saved Experiments"
  history group, restores a saved record by `record_id` through the application
  boundary, and enables "Open Existing Experiment" (reopen most recent saved)
  only when persisted records exist.
- The AppKit controller loads persisted history after navigation and handles the
  `open_experiment` message; a failed listing degrades to an empty timeline
  rather than blocking launch.

## Files Changed

- `labassistant/application.py`
- `labassistant/ui/presenters.py`
- `labassistant/ui/web_workspace.py`
- `labassistant/ui/macos_window.py`
- `tests/test_application.py`
- `tests/test_desktop.py`
- `docs/architecture/capabilities.md`
- `docs/ROADMAP.md`
- `docs/status/current-state.md`
- `docs/prompts/010-promote-persisted-experiment-listing.md`

## Test Results

- Focused application and desktop tests: 22 passed.
- Full suite: 142 passed (was 135; +7 new tests) with the existing fixtures.
- Clean-process import of the AppKit controller succeeded and the controller
  exposes the new restore handler.
- End-to-end scratch run confirmed newest-first listing, metadata-only payload
  with readable time, and restore rendering through the shared read model.

## Remaining Work

- Restore currently assembles a DLS read model; generalize when a second
  persisted technique exists.
- "Open Existing Experiment" reopens the most recent saved record; a native
  record picker can come with desktop packaging.
- Desktop visual QA of the persisted timeline on additional macOS display sizes
  remains part of the packaging track.
