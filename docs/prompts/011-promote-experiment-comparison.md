# Promote Experiment Comparison Into The Application Layer

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 010 - Promote Persisted Experiment Listing

## Objective

Add a versioned, read-only application query for comparing current DLS evidence
with a selected or latest persisted experiment, then route the Streamlit history
panel through it without changing the established drift calculations.

## Context

Listing and restore crossed the application boundary in task 010, but Streamlit
still selected a saved record and called the history-layer comparison DataFrame
directly. That left comparison math and its mutable presentation shape exposed
to shells.

## Tasks

- Add immutable experiment-comparison and sample-row read models.
- Select a specific baseline record or the latest eligible history record.
- Reuse history-owned sample matching and drift thresholds.
- Register the application capability and route Streamlit through it.
- Cover drift, sample matching, absent history, and contract serialization.

## Deliverables

- Application comparison contract and capability registration.
- Streamlit caller using the application boundary.
- Focused tests and aligned architecture/status documentation.

## Success Criteria

A shell compares current evidence with persisted history through a versioned
application capability, receives immutable rows, and does not reimplement drift
math.

## Implementation Summary

- Added frozen `ExperimentComparison` and `ExperimentComparisonRow` read models.
- Added `compare_experiments`, supporting an explicit baseline ID or the latest
  eligible saved record and returning an explicit no-baseline result.
- Kept sample-name matching and Z-average/PDI drift thresholds in
  `labassistant.history`; the application layer only selects and translates.
- Registered the capability and moved the Streamlit history panel to it.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/011-promote-experiment-comparison.md`

## Test Results

- Focused application and history tests: 27 passed.
- Full suite: 144 passed in 2.08s (was 142; +2 application tests).
- `git diff --check` passed and the knowledge graph was refreshed.

## Remaining Work

- Promote similar-experiment search when a shell is ready to consume a typed
  application result.
- Generalize comparison beyond DLS when a second persisted technique has stable
  comparison semantics.
