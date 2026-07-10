# Canonicalize Lot-Level DLS Derived Metrics

Status: Complete
Created: 2026-07-10
Completed: 2026-07-10
Priority: High
Depends On: 005 - Promote Persisted Experiment Retrieval

## Objective

Define and enforce one evidence-selection rule for lot-level DLS
`derived_metrics`, replacing the implicit use of intensity replicate 1.

## Evidence Rule

Lot-level distribution metrics use the averaged backscatter intensity curve
when it is available. Backscatter is the canonical sizing view; forward-angle
curves remain separate, aggregation-sensitive evidence. A single available
angle uses its averaged curve. When per-angle assignment is unavailable, all
valid intensity replicates are averaged. The legacy intensity curve is the
final compatibility fallback. Volume and number distributions are never
substituted for intensity evidence.

## Implementation Summary

- Moved metric refresh after replicate-to-angle assignment.
- Centralized canonical intensity evidence selection and recorded the selected
  source in measurement provenance.
- Extended angle assignment to support a single summarized angle.
- Added synthetic fallback coverage and updated representative dual-angle
  fixture expectations to the averaged backscatter evidence.

## Files Changed

- `labassistant/importers/measurement_importer.py`
- `tests/test_multi_file_importer.py`
- `tests/test_real_fixtures.py`
- `docs/ARCHITECTURE.md`
- `docs/prompts/006-canonicalize-lot-level-dls-derived-metrics.md`
- `docs/status/current-state.md`

## Success Criteria

Lot-level metrics are reproducible from the best available intensity evidence,
their source is explicit, single-angle and unassigned-replicate fallbacks are
covered, and representative real-file behavior is protected.

## Test Results

- Focused importer and representative-fixture tests: 15 passed.
- Full suite: 126 passed in 2.03s.

## Remaining Work

- Add representative fixtures for more vendor versions, locales, delimiters,
  workbook layouts, single-angle exports, and volume/number distributions.
