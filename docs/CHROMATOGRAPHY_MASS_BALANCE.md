# Chromatography And Mass Balance Proposal

LabAssistant should eventually help scientists investigate mass-balance issues
by turning chromatographic data into observations, hypotheses, and recommended
follow-up work. This is a future module, not full HPLC support.

## Scope

The first chromatography module should answer:

- Is the parent compound decreasing?
- Are impurity or degradation peaks increasing correspondingly?
- Is total chromatographic area conserved?
- Are unknown peaks appearing?
- Are peaks shifting, broadening, or co-eluting?
- Are replicate results reproducible?
- Could missing mass be due to recovery, preparation loss, detector response,
  precipitation, aggregation, or integration choices?

## Minimal Models

The initial code-level models are:

- `ChromatographyPeak`: one peak with identity/role, retention time, area,
  width, tailing, resolution, and integration metadata.
- `ChromatographyMeasurement`: one instrument run with peaks, total area,
  recovery, replicate RSD, baseline status, method, injection, and source files.
- `MassBalanceAssessment`: interpretation-level deltas such as parent change,
  impurity change, unknown area, total area change, recovery, reproducibility,
  hypotheses, recommendations, and generated observations.

These models live in `labassistant.models` for now to avoid a disruptive package
split. Future work can move them to `models/chromatography.py` once the project
has a package-based model layout.

## Observation Mapping

Chromatography should generate normalized `Observation` objects rather than
directly driving UI decisions. Examples:

| Chromatography signal | Observation |
| --- | --- |
| parent area falls below threshold | Parent peak decreased |
| known impurity area rises | Known impurity increased |
| unknown peak area appears | Unknown peak appeared |
| total chromatographic area falls | Total area decreased |
| retention time differs from reference | Retention time shifted |
| peak width increases | Peak broadened |
| tailing factor increases | Peak tailing increased |
| baseline status is not stable | Baseline changed |
| integration boundaries differ from reference | Integration boundary changed |
| replicate RSD is elevated | Replicate %RSD elevated |
| recovery is low | Recovery control failed |

The current minimal helper module, `labassistant.chromatography`, can create
observations from populated chromatography models. It does not parse HPLC files.

## Hypothesis Mapping

Mass-balance observations should suggest hypotheses such as:

- Incomplete recovery
- Degradation into detected impurities
- Degradation into non-detected species
- Degradation into unknown chromatographic species
- Co-elution
- Integration error
- Matrix effect
- Detector response-factor mismatch
- Adsorption/sample prep loss
- Insoluble aggregate/precipitate formation
- Method instability

These hypotheses should remain evidence-linked and conservative. They are not
claims of cause; they are ranked investigation paths.

## Cross-Instrument Reasoning

The key product value is cross-instrument reasoning. If DLS observations include
aggregation, broad particle-size distribution, or a large-particle tail, while
chromatography observations include reduced recovery or unexplained total area
loss, LabAssistant should raise:

> Missing mass may be associated with insoluble or aggregated material.

That hypothesis links a chromatographic mass-balance gap to a particle-quality
observation without pretending either instrument proves the mechanism alone.

## Incremental Build Plan

1. Keep current DLS/Zetasizer behavior unchanged.
2. Keep chromatography support model-first and parser-free.
3. Allow manually populated `ChromatographyMeasurement` and
   `MassBalanceAssessment` objects to generate `Observation` objects.
4. Add a future ingestion adapter only after example HPLC/SEC exports are
   available.
5. Add report sections that combine DLS and chromatography observations into one
   experiment-level interpretation.
