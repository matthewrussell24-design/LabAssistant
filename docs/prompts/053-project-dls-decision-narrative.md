# Project DLS Decision And Narrative Inputs From Measurements

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 052 - Project DLS Review Evidence From Measurements

## Objective

Route DLS decision ranking and narrative interpretation through
`DLSMeasurementMetrics` rather than mutable workspace metrics and warnings.

## Context

Tasks 051 and 052 made shared metrics/status, review wording, and sample
summaries Measurement-first. Attention scoring, warning table rows, and the
narrative distribution-confidence check still read compatibility fields.

## Tasks

- Add authoritative distribution-evidence availability to the frozen metrics
  projection.
- Move attention score inputs and warning penalties to projected values/flags.
- Preserve `sample_attention_score(sample, medians)` as a compatibility wrapper.
- Build attention rows from projected status, warnings, and review evidence.
- Use Measurement distributions for narrative confidence wording.
- Preserve score weights, tie-breaking, warning order, text, and dataframe
  schemas.
- Prove mutable workspace overrides cannot alter decision or narrative output.

## Deliverables

- Measurement-first attention scoring and attention-table composition.
- Measurement-first distribution-confidence check.
- Decision/narrative divergence regression coverage.

## Success Criteria

Decision and narrative paths in `labassistant.interpretation` do not read
`sample.metrics` or `sample.warnings`, existing application output remains
unchanged, and observation/distribution projection work remains separately
bounded.

## Implementation Summary

- Added authoritative distribution-evidence availability to the frozen
  `DLSMeasurementMetrics` projection.
- Added Measurement-first attention scoring while preserving the established
  sample-based compatibility function.
- Routed attention status, reasons, warning columns, score penalties, and all
  score inputs through projected Measurement evidence.
- Replaced narrative distribution-column compatibility checks with authoritative
  Measurement distribution availability.
- Preserved ranking weights, alphabetical tie-breaking, warning ordering,
  wording, and dataframe schemas.
- Added divergence coverage proving mutable workspace metric, warning, and
  distribution-column overrides cannot alter decision or narrative results.

## Files Changed

- `labassistant/dls_evidence.py`
- `labassistant/interpretation.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/053-project-dls-decision-narrative.md`

## Test Results

- Focused decision and narrative coverage: 6 passed in 1.12s.
- Full suite: 230 passed in 2.35s.
- Python compile verification, status-page link checks, and `git diff --check`
  passed.
- Verified `labassistant.interpretation` has no direct `sample.metrics` or
  `sample.warnings` reads.
- Headless Streamlit startup and health smoke passed on port 8765.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Route DLS observation normalization through authoritative Measurement flags
  and projected metrics while preserving observation ordering and exact text.
