# Promote Research Journal Read And Export Workflows

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 017 - Promote Related Scientific Context Retrieval

## Objective

Expose Research Journal listing, filtering, and Markdown export through a
versioned immutable application contract while keeping note creation separate.

## Tasks

- Add immutable journal entry and query-result read models.
- Preserve grouping, newest-first ordering, and keyword/tag/instrument/sample filters.
- Preserve the established Markdown export exactly.
- Register a read capability and migrate Streamlit listing/export callers.
- Keep standalone note creation as an explicit write through `KnowledgeStore`.

## Success Criteria

Streamlit lists and exports journal entries through the application layer
without constructing `ResearchJournal`, while note creation remains a distinct
user-triggered write.

## Implementation Summary

- Added frozen grouped journal-entry and query-result read models.
- Added and registered `retrieve_research_journal`, preserving grouping,
  newest-first ordering, all four filters, and the existing Markdown exporter.
- Routed Streamlit's journal table and download through the application query.
- Kept standalone note creation as a separate user-triggered `KnowledgeStore` write.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/018-promote-research-journal-reads.md`

## Test Results

- Focused application and context-engine tests: 38 passed.
- Full suite: 160 passed in 2.12s.
- Headless Streamlit startup smoke passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote standalone scientific-note creation into an explicit application
  command with validation and immutable receipt metadata.
