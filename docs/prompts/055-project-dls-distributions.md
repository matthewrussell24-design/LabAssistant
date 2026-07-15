# Project DLS Distributions From Measurements

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 054 - Project DLS Observations From Measurements

## Objective

Route the immutable DLS distribution projection through authoritative
`Measurement.distributions` and projected status instead of mutable workspace
dataframes and column-name metrics.

## Tasks

- Reuse one canonical Measurement distribution selector.
- Project intensity, volume, and number values directly from `DistributionData`.
- Preserve filtering, sorting, peak detection, signal ordering, empty fallback,
  volume/number-only behavior, and the immutable result shape.
- Tighten validation around authoritative Measurement evidence.
- Prove workspace dataframe, metric, and warning mutations cannot alter results.

## Success Criteria

`retrieve_dls_distributions` does not read `sample.data`, `sample.metrics`, or
`sample.warnings`; distribution regressions remain unchanged; arbitrary raw
table inspection remains a separate workspace adapter concern.

## Implementation Summary

- Reused one canonical Measurement distribution selector.
- Projected intensity, volume, and number directly from `DistributionData`.
- Preserved filtering, sorting, peaks, signal order, identified-empty behavior,
  fallback, projected status, and the immutable result.
- Added divergence coverage for workspace mutations and volume/number-only data.

## Test Results

- Focused distribution and peak coverage: 15 passed.
- Full suite: 232 passed in 2.52s.

## Remaining Work

- Isolate arbitrary raw DLS table inspection behind a dedicated raw-source
  adapter contract.
