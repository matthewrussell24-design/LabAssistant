# Project DLS Observations From Measurements

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 053 - Project DLS Decision And Narrative Inputs From Measurements

## Objective

Route DLS observation normalization through authoritative Measurement flags and
`DLSMeasurementMetrics` instead of mutable workspace warnings and metrics.

## Context

Task 053 removed the final compatibility reads from DLS interpretation.
Observation normalization still iterates `sample.warnings` and looks up six
values in `sample.metrics`, even though Measurement contains the same evidence.

## Tasks

- Iterate warning labels in Measurement flag order.
- Resolve PDI, secondary peak, tail, width, aggregation index, and correlogram
  noise from `DLSMeasurementMetrics`.
- Preserve sample name and source ID compatibility at the wrapper boundary.
- Keep dual-angle category, confidence, corroboration, and recommendation in
  Measurement provenance.
- Preserve observation ordering, duplicate handling, exact evidence text,
  severity, categories, confidence, and recommendations.
- Tighten application validation around authoritative Measurement evidence.
- Prove mutable workspace overrides cannot alter normalized observations.

## Deliverables

- Measurement-first DLS observation normalization.
- Measurement-based application validation.
- Observation divergence and ordering regression coverage.

## Success Criteria

`labassistant.observations` does not read `sample.metrics` or `sample.warnings`,
all observation and experiment-brief regressions remain unchanged, and raw
distribution projection is the only explicitly bounded workspace-table
dependency.

## Implementation Summary

- Iterated DLS warnings in authoritative Measurement flag order and preserved
  duplicate labels.
- Resolved PDI, secondary peak, tail, width, aggregation index, and correlogram
  noise through `DLSMeasurementMetrics`.
- Preserved sample display name/source ID compatibility and kept dual-angle
  category, confidence, corroboration, and recommendation in Measurement
  provenance.
- Removed the compatibility `_metric` lookup and tightened application
  validation to require Measurement evidence.
- Updated synthetic integration fixtures to model authoritative values/flags.
- Added divergence coverage proving workspace metric/warning changes cannot
  alter observation ordering or content.

## Files Changed

- `labassistant/observations.py`
- `labassistant/application.py`
- `tests/test_observations.py`
- `tests/test_application.py`
- `tests/test_cross_technique_investigation.py`
- `tests/test_memory_app_integration.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/054-project-dls-observations.md`

## Test Results

- Focused observation/application/cross-technique coverage: 8 passed in 1.01s.
- Full suite: 231 passed in 2.28s.
- Python compile verification, status-page link checks, and `git diff --check`
  passed.
- Verified `labassistant.observations` has no direct `sample.metrics` or
  `sample.warnings` reads.
- Headless Streamlit startup and health smoke passed on port 8765.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Migrate the immutable DLS distribution projection to
  `Measurement.distributions` while preserving signal selection, filtering,
  sorting, peaks, and empty behavior; keep arbitrary raw-table inspection
  separate.
