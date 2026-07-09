# LabAssistant Vision & Roadmap

This file is kept for compatibility with earlier project handoffs. The project
brain is now split into focused documents:

1. `docs/VISION.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `docs/AGENT_HANDOFF.md`

## Current Vision

LabAssistant is an Experiment Intelligence Platform that transforms laboratory
data into scientific insight across the lifecycle of a scientific experiment.

The Zetasizer/DLS workflow is the first supported use case, not the final
product. The core product goal is:

```text
Define or upload an experiment -> LabAssistant gathers observations from every
available measurement, explains what happened, whether the result is
trustworthy, why it matters, and what to do next.
```

The intelligence layer is the product. Instruments are plugins. Experiments are
first-class objects. Measurements are building blocks.

Current scientific direction: LabAssistant should reason from experimentally
relevant relationships first. For the active DLS work, the primary investigation
is whether explicitly entered total circulation time relates to forward-angle
mean Z-average and forward-angle mean PDI. Circulation time must be entered or
imported as an experimental variable; it should not be inferred from lot number,
file order, or other incidental metadata.

The next planned orthogonal experiment is filtration testing on the same
samples. The working hypothesis chain is:

```text
circulation time -> forward-scatter size/PDI -> filtration difficulty
```

Filtration is expected to strengthen or weaken the relationship hypothesis
because it measures sample behavior outside the DLS analysis itself.

The first filtration workflow is intentionally conservative and reproducible:
filtration difficulty is a 1-5 ordinal operator-assessed rubric, pressure is
stored in the entered unit and normalized to kPa for supported units (`Pa`,
`kPa`, `bar`, `psi`), and generic CSV import is limited to simple tabular
measurements rather than proprietary device parsing. Relationships involving
the ordinal difficulty score should use Spearman rank correlation; continuous
DLS/circulation relationships can continue to use Pearson correlation when
valid.

Saved DLS experiments can be loaded back into editable UI state, but history
remains append-only. Edited/restored experiments should be saved as new versions
with lineage provenance rather than silently mutating historical records.

`FiltrationMeasurement` includes optional generic trace fields for future
pressure-over-time or flow-rate outputs so real device files can be supported
without another model rewrite.

The Malvern-derived dual-angle Aggregation Index remains useful supporting
multi-detector evidence, but it is no longer the headline trend metric for this
larger-particle system. Its published small-protein aggregation thresholds may
not transfer directly and should not gate or override direct forward-scatter
trend analysis.

Every experiment should answer:

1. What happened?
2. Is it real/trustworthy?
3. Why does it matter?
4. What should the scientist do next?

## Current Roadmap Summary

The safest next move is not a rewrite. Keep the working Zetasizer workflow stable
while introducing compatibility-first experiment-centered boundaries:

1. Preserve the current `Experiment` / `Observation` / `Measurement` structure.
2. Keep chromatography import, mass-balance reasoning, OpenLab OLAX work,
   KnowledgeStore/context retrieval, and Research Journal behavior stable.
3. Keep pure relationship, reproducibility, and anomaly helpers in
   `trend_analysis.py` or similarly small reusable modules rather than burying
   scientific logic directly in Streamlit UI code.
4. Continue adding tests that prove compatibility boundaries and scientific
   helper behavior.

See `docs/ROADMAP.md` for the full phased plan.
