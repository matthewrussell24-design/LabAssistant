# Promote Standalone Scientific Note Creation

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 018 - Promote Research Journal Read And Export Workflows

## Objective

Promote the explicitly confirmed standalone journal-note write into a validated
application command with immutable receipt metadata.

## Tasks

- Validate non-empty note text before persistence.
- Normalize the optional title, instrument identifier, and tags.
- Persist exactly one human note through an injectable local store.
- Return immutable item identity, provenance, tags, and timestamp metadata.
- Register the command for Human UI and CLI callers only and migrate Streamlit.

## Success Criteria

Streamlit's Add Journal Note button calls a registered application command and
does not construct storage directly; no autonomous or future-API write access is implied.

## Implementation Summary

- Added a frozen, versioned scientific-note receipt that omits note content.
- Added `add_scientific_note` with required-text validation and normalization
  for title, instrument, and tags before one local write.
- Registered the command for Human UI and CLI callers only, explicitly excluding
  Agent and Future API access.
- Routed Streamlit's confirmed Add Journal Note action through the command and
  removed its direct `KnowledgeStore` construction.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/019-promote-scientific-note-command.md`

## Test Results

- Focused application and context-engine tests: 40 passed.
- Full suite: 162 passed in 2.21s.
- Headless Streamlit startup smoke passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote Streamlit's chromatography/OpenLab import-analysis orchestration into
  a typed application workflow, matching the existing DLS dataset boundary.
