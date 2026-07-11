# Promote Experiment Brief Preview

Status: Complete
Created: 2026-07-11
Last Updated: 2026-07-11
Priority: High
Depends On: 023 - Promote Normalized Observation Generation

## Objective

Promote the generic experiment-level brief into an immutable, Experiment-first
application workflow without adding export or presentation concerns.

## Context

Streamlit assembled its Experiment Brief directly from the Investigator result.
The deterministic reasoning was reusable, but the report-preview composition had
no stable application contract.

## Tasks

- Accept an `Experiment` as the authoritative input.
- Compose, rather than duplicate, the existing Investigator capability.
- Return a deeply immutable experiment header, report sections, and observation evidence.
- Keep DLS-only decision ranking and document export outside this contract.
- Register the workflow and migrate Streamlit's generic Experiment Brief.

## Deliverables

- `produce_experiment_brief` capability.
- Frozen experiment identity, section, and preview read models.
- Application and Streamlit compatibility coverage.

## Success Criteria

Streamlit obtains its generic Experiment Brief through one registered
Experiment-first capability whose serialized output contains no mutable domain
objects, DataFrames, UI markup, or export formatting.

## Implementation Summary

- Added frozen `ExperimentBriefIdentity`, `ExperimentBriefSection`, and
  `ExperimentBriefPreview` contracts.
- Added `produce_experiment_brief`, which validates the input and composes
  `investigate_experiment` into stable report sections and evidence.
- Registered the capability for Human UI, Agent, CLI, and Future API callers.
- Routed Streamlit's generic Experiment Brief renderer through the new preview.
- Preserved the separate DLS-specific Decision Brief without widening this contract.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/024-promote-experiment-brief.md`

## Test Results

- Focused application and Investigator tests: 51 passed.
- Full suite: 173 passed in 2.58s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the remaining DLS import-preview orchestration or hypothesis generation,
  based on the next compatibility-first application-layer slice.
