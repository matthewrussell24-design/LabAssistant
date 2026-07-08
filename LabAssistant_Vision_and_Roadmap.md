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

Every experiment should answer:

1. What happened?
2. Is it real/trustworthy?
3. Why does it matter?
4. What should the scientist do next?

## Current Roadmap Summary

The safest next move is not a rewrite. Keep the working Zetasizer workflow stable
while introducing compatibility-first experiment-centered boundaries:

1. Add a first-class `Experiment` model/envelope around the current
   `Measurement` list.
2. Add an `ingestion/zetasizer.py` facade over the current DLS importer.
3. Add a `reasoning/experiment_brief.py` facade over the current decision brief
   logic.
4. Extract pure reproducibility and anomaly helpers from `trend_analysis.py`
   behind compatibility imports.
5. Add a non-conflicting `particle_size_metrics.py` module behind the existing
   `metrics.py` compatibility module; later convert to `metrics/particle_size.py`
   when the package split is worth the churn.
6. Add tests that prove old and new import paths both work.

See `docs/ROADMAP.md` for the full phased plan.
