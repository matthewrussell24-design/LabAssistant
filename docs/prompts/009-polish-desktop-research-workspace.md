# Polish the Desktop Research Workspace

Status: Complete
Created: 2026-07-10
Priority: High
Depends On: 008 - Desktop Prototype Vertical Slice

## Objective

Transform the functional PySide6 prototype into a calm, modern research
workspace that feels like a laboratory second brain rather than a file viewer.
This is a presentation-layer redesign. Scientific calculations, analysis
behavior, application contracts, and domain models remain unchanged.

## Product Experience

The home screen should establish four clear regions:

- **Workspace:** action-oriented experiment entry points, led by New Experiment
  and Import DLS Dataset.
- **Current Experiment:** the visual focus, with purposeful empty and populated
  states plus concise result cards.
- **History:** a clickable timeline of analyses performed during the current
  desktop session. Persisted history remains out of scope until a desktop-safe
  list/restore application contract exists.
- **Analysis:** structured summary, evidence, causal-assessment boundary, and
  next-step guidance based only on the existing application read model.

Unavailable capabilities such as chromatography import, generic CSV import,
and persisted experiment restore should be visible as scalable future actions
but clearly disabled. The UI must not imply that they work.

## Architecture

- Keep `labassistant.desktop` as the launcher/controller only.
- Add reusable PySide6 presentation components such as `Card`, `StatusBadge`,
  `MetricTile`, `WorkspaceAction`, `HistoryItem`, and `AnalysisSection`.
- Keep theme tokens and QSS separate from layout/controller code.
- Derive display copy through pure presentation helpers over
  `DLSAnalysisResult`; do not calculate or reinterpret scientific metrics.
- Keep all import and analysis calls routed through `analyze_dls_dataset`.

## Visual Direction

- Off-white workspace, white cards, restrained blue accent, and semantic green,
  amber, and red.
- Spacious hierarchy, rounded cards, soft shadows, minimal borders, and system
  typography.
- Subtle hover states, loading feedback, and fade-in transitions.
- Avoid giant raw-text panels, excessive gradients, skeuomorphism, and dense
  enterprise dashboard styling.

## Non-Goals

- New scientific features, calculations, models, or instrument support.
- Authentication, HTTP APIs, agents, packaging, or persistence redesign.
- Pretending that disabled future actions or persisted desktop history already
  exist.
- Redesigning or removing the compatible Streamlit shell.

## Success Criteria

The native app opens into a polished dashboard, the verified DLS file-selection
workflow still runs end to end, results appear as reusable cards and structured
analysis sections, session-history cards restore prior views, disabled future
actions are honest, and visual QA confirms the hierarchy at realistic macOS
window sizes.

## Implementation Summary

- Replaced the prototype text panel with a three-column research workspace:
  action-oriented Workspace, visually dominant Current Experiment, structured
  Analysis, and clickable session History.
- Added separate theme tokens/QSS, pure presentation helpers, reusable PySide6
  components, and a dedicated `DesktopWindow` controller/layout module.
- Added purposeful empty and populated experiment states, metric tiles,
  measurement cards, semantic badges, soft shadows, hover states, loading
  feedback, and a short fade-in transition.
- Kept unavailable chromatography, generic CSV, and persisted-history actions
  visibly disabled instead of simulating unsupported behavior.
- Preserved the existing `analyze_dls_dataset` call and made no changes to
  scientific calculations, analysis logic, application contracts, or models.
- Organized analysis into Summary, Evidence, Possible Causes, and Suggested
  Next Steps. The causes section explicitly states the current contract cannot
  assign causality, preventing presentation code from inventing conclusions.
- Added clickable in-session history cards that restore prior result views.

## Files Changed

- `labassistant/desktop.py`
- `labassistant/ui/theme.py`
- `labassistant/ui/presenters.py`
- `labassistant/ui/components.py`
- `labassistant/ui/desktop_window.py`
- `tests/test_desktop.py`
- `tests/test_desktop_ui.py`
- `docs/ARCHITECTURE.md`
- `docs/STANDALONE_APP.md`
- `docs/ROADMAP.md`
- `docs/prompts/009-polish-desktop-research-workspace.md`
- `docs/status/current-state.md`

## Test Results

- Focused desktop, UI-component, and application tests: 16 passed.
- Full suite: 136 passed in 3.04s.
- Streamlit headless startup: successful on port 8765.
- Native macOS visual QA: populated dashboard, empty state, and session-history
  restore verified with the representative Lot 1 DLS dataset.

## Remaining Work

- Promote persisted experiment listing/restoration through the application
  boundary before enabling Open Existing Experiment or persistent timeline
  cards in the desktop shell.
- Validate typography and spacing on additional target Mac display sizes before
  packaging.
