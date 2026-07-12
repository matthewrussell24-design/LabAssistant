# Promote DLS Data Analysis

Status: Complete
Created: 2026-07-12
Last Updated: 2026-07-12
Priority: High
Depends On: 027 - Promote DLS Narrative Composition

## Objective

Promote detailed DLS data-analysis composition into the existing immutable
narrative workflow while preserving its deterministic sections and wording.

## Context

Automated findings and the trend story cross `compose_dls_narrative`, but
Streamlit's diagnostics expander still calls `build_data_analysis` directly and
passes a pandas metrics table into it.

## Tasks

- Extend the existing narrative result with ordered detailed-analysis sections.
- Reuse the workflow's internally built metrics table.
- Delegate text generation to the established interpretation helper.
- Migrate Streamlit's Data Analysis cards without changing their layout.
- Preserve exact headings, bullets, validation, and rule-based behavior.

## Deliverables

- Additive detailed-analysis output on `DLSNarrative`.
- Streamlit migration and exact-output compatibility tests.
- Updated capability and handoff documentation.

## Success Criteria

Streamlit renders detailed DLS analysis from the single registered
`compose_dls_narrative` call and no longer imports `build_data_analysis`.

## Implementation Summary

- Added ordered `detailed_analysis` sections to the existing immutable
  `DLSNarrative` result.
- Reused the single internally built metrics table and delegated exact wording
  to the established `build_data_analysis` helper.
- Routed Streamlit's Data Analysis cards through the already-composed narrative
  and removed its direct builder import.
- Expanded compatibility coverage to compare every heading and bullet against
  the established helper output.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/028-promote-dls-data-analysis.md`

## Test Results

- Focused application, interpretation, and trend tests: 63 passed.
- Full suite: 179 passed in 2.48s.
- Headless Streamlit startup smoke passed.

## Remaining Work

- Promote the DLS health-strip score, status counts, and medians into an
  immutable application read model.
