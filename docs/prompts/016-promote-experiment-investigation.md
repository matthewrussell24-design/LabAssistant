# Promote Experiment Investigation Into The Application Layer

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 015 - Add A Cross-Technique Investigation Case

## Objective

Expose the instrument-independent Investigator through a versioned immutable
application contract and route Streamlit's Experiment Brief through it.

## Tasks

- Translate Investigator findings and normalized observation evidence into frozen read models.
- Preserve the five canonical questions, completeness, interpretability, and confidence behavior.
- Register `investigate_experiment` in the capability catalog.
- Route the Streamlit Experiment Brief and observation table through the contract.
- Test serialization, immutability, empty evidence, and the shell-facing result.

## Success Criteria

Streamlit renders an investigation obtained through a registered immutable
application capability without calling the Investigator or observation brief
builder directly.

## Implementation Summary

- Added frozen finding, observation-evidence, and investigation read models.
- Added and registered `investigate_experiment`, translating the existing
  deterministic report without changing Investigator rules.
- Preserved observation source type, source ID, sample, confidence, evidence,
  recommendation, severity counts, and all five canonical questions.
- Routed Streamlit's Experiment Brief and observation table through the
  application contract and removed its direct brief-builder dependency.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/016-promote-experiment-investigation.md`

## Test Results

- Focused application, Investigator, and observation tests: 36 passed.
- Full suite: 155 passed in 2.01s.
- Headless Streamlit startup smoke passed on port 8765.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote related scientific context retrieval into the application layer and
  route the existing Streamlit context panel through a typed read contract.
