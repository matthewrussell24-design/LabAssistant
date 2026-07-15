# Project DLS Review Evidence From Measurements

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 051 - Project DLS Metrics From Measurements

## Objective

Route DLS warning-evidence wording and immutable per-sample summaries through
`DLSMeasurementMetrics` instead of mutable workspace metrics and warnings.

## Context

Task 051 established a frozen Measurement-first metrics/status projection.
`review_evidence` and `summarize_dls_samples` still reconstruct the same values
from `sample.metrics` and `sample.warnings`, leaving application output open to
workspace dictionary drift.

## Tasks

- Add a projection-based formatter for ordered warning evidence.
- Preserve `review_evidence(sample)` as a compatibility wrapper.
- Route required and optional sample-summary display rows through
  `DLSMeasurementMetrics`.
- Source summary warnings and status from Measurement flags.
- Preserve exact wording, formatting, warning order, and optional-row behavior.
- Prove mutable workspace metric/warning overrides cannot alter the summary.

## Deliverables

- `review_evidence_from_metrics`.
- Measurement-first `summarize_dls_samples` implementation.
- Compatibility and divergence regression coverage.

## Success Criteria

Review-evidence formatting and immutable sample summaries do not read
`sample.metrics` or `sample.warnings`, existing scientist-facing output remains
unchanged, and compatibility-only distribution fields remain explicitly scoped.

## Implementation Summary

- Added `review_evidence_from_metrics` with the established warning order,
  metric formatting, aggregation fallback, and missing-distribution wording.
- Preserved `review_evidence(sample)` as a Measurement-first compatibility
  wrapper.
- Routed required and optional immutable sample-summary rows, warnings, status,
  and review evidence through one `DLSMeasurementMetrics` projection per sample.
- Tightened sample-summary and health validation around authoritative
  `Measurement` evidence.
- Added divergence coverage proving mutable workspace metric and warning
  overrides do not alter immutable sample summaries.

## Files Changed

- `labassistant/interpretation.py`
- `labassistant/application.py`
- `tests/test_application.py`
- `tests/test_interpretation.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/052-project-dls-review-evidence.md`

## Test Results

- Focused review-evidence, sample-summary, and health coverage: 6 passed in
  0.62s.
- Full suite: 229 passed in 2.42s.
- Python compile verification, status-page link checks, and `git diff --check`
  passed.
- Headless Streamlit startup and health smoke passed on port 8765.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Route decision ranking and narrative interpretation helpers through
  `DLSMeasurementMetrics`, preserving score weights, tie-breaking, warning
  ordering, wording, and dataframe compatibility.
