# Promote Filtration Relationship Hypothesis

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 047 - Promote DLS Experiment Brief Inputs

## Objective

Promote the qualified filtration relationship hypothesis into an immutable
application read instead of authoring the scientific claim in a static
Streamlit callout.

## Context

The filtration trend capability already returns qualified Spearman summaries
with minimum-evidence constraints and correlation-only language. Streamlit
still owns a static cross-technique working hypothesis before rendering those
application results.

## Tasks

- Add a frozen, versioned filtration relationship hypothesis read.
- Compose it from `DLSForwardScatterTrendRead` and `FiltrationTrendRead` without
  recomputing correlations or qualifying the full hypothesis from partial
  evidence.
- Preserve the circulation-time, forward-size/PDI, and orthogonal-filtration
  hypothesis with cautious, non-causal wording.
- Keep the hypothesis visible before sufficient evidence exists while clearly
  labeling it proposed rather than supported.
- Report how many of the five component relationships are currently estimable,
  distinguish insufficient, partial, and fully qualified evidence, and preserve
  the underlying qualified messages.
- Register the read for Human UI, CLI, and Future API callers.
- Route Streamlit's callout through application-provided text.
- Add insufficient, qualified, immutable, validation, and registry coverage.

## Deliverables

- `generate_filtration_relationship_hypothesis` capability.
- Frozen `FiltrationRelationshipHypothesis` read model.
- Streamlit callout migration.

## Success Criteria

Streamlit renders application-provided, evidence-qualified hypothesis text and
contains no presentation-authored filtration relationship claim.

## Implementation Summary

- Added a frozen, versioned hypothesis read composed from the existing immutable
  circulation/forward-scatter and filtration trend results without recomputing
  their five component relationships.
- Preserved the cross-technique working hypothesis and orthogonal follow-up
  framing while distinguishing insufficient/proposed, partially qualified, and
  fully qualified estimable evidence.
- Included all five underlying relationship messages and explicit
  correlation-only, non-causal wording whenever estimates are available.
- Registered the read for Human UI, CLI, and Future API callers while retaining
  the existing Agent exclusion for ordinal operator-assessed evidence.
- Migrated Streamlit to render only application-provided hypothesis text after
  reviewed session evidence is applied and trend qualification is complete.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/048-promote-filtration-relationship-hypothesis.md`

## Test Results

- Focused hypothesis and capability-registry tests: 7 passed.
- Full suite: 224 passed in 2.53s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Audit the remaining direct Streamlit-to-core imports to distinguish legitimate
  presentation/input concerns from true application-boundary gaps before
  declaring the extraction milestone mature.
