# Promote DLS Aggregation Assessment

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 032 - Promote Filtration Follow-Up Trends

## Objective

Promote dual-angle DLS aggregation assessment into an immutable application
workflow while preserving paired evidence, thresholds, confidence, checklist,
and unavailable behavior.

## Context

Streamlit still calls `assess_dual_angle_aggregation` for each parsed sample and
renders mutable domain results directly.

## Tasks

- Accept parsed DLS samples and assess every measurement.
- Preserve nested forward/back angle evidence and assessment provenance.
- Return immutable checklist, flags, category, confidence, and guidance.
- Include unavailable assessments rather than silently dropping samples.
- Register the workflow and migrate Streamlit rendering.

## Deliverables

- `assess_dls_aggregation` capability.
- Frozen angle, checklist, assessment, and result read models.
- Streamlit migration and compatibility tests.

## Success Criteria

Streamlit renders dual-angle aggregation comparison and checklist content from
one registered immutable application result and no longer imports the domain
assessment function.

## Implementation Summary

- Added frozen `DLSAngleEvidence`, `DLSAggregationCheck`,
  `DLSAggregationAssessment`, and `DLSAggregationRead` contracts.
- Added `assess_dls_aggregation`, which assesses every parsed sample, preserves
  nested evidence and checklist provenance, and retains unavailable results.
- Registered the workflow for Human UI, CLI, and Future API callers while
  excluding Agent access.
- Routed Streamlit cards, charts, selectors, checklist, and summary content
  through immutable assessment values while keeping distribution overlays in
  the visualization layer.
- Preserved category thresholds, confidence, corroboration, guidance, and
  unavailable explanations.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/033-promote-dls-aggregation-assessment.md`

## Test Results

- Focused application and aggregation tests: 73 passed.
- Full suite: 189 passed in 2.52s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote per-sample DLS status, warning evidence, and inspection summaries into
  an immutable presentation-neutral application workflow.
