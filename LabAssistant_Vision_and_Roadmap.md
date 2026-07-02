# LabAssistant Vision & Roadmap

## Vision

LabAssistant is **not** a CSV viewer.

It is an AI-powered scientific analysis platform that sits on top of
laboratory instruments and helps scientists understand experimental data
faster.

The first supported instrument is the **Malvern Zetasizer**, but the
architecture should be flexible enough to support additional instruments
in the future.

The guiding question for every feature is:

> **"What should the scientist know that isn't immediately obvious from
> the instrument software?"**

------------------------------------------------------------------------

# Product Philosophy

The application should help scientists make decisions, not simply
display data.

Every screen should answer:

-   Should I trust this measurement?
-   Does anything deserve my attention?
-   Which sample is the best?
-   Which sample is the worst?
-   Why?

Avoid unnecessary charts and clutter. Favor clear conclusions backed by
transparent data.

------------------------------------------------------------------------

# Project Direction

The current application is a working Streamlit dashboard.

The next phase is to build a robust scientific analysis engine.

Rather than treating imported files as disconnected inputs, the
application should build a complete **Measurement** object representing
one DLS experiment.

------------------------------------------------------------------------

# Core Architecture

## Measurement

Each experiment should become one unified object.

``` text
Measurement
│
├── Metadata
│   ├── Sample name
│   ├── Date / Time
│   ├── Instrument
│   ├── Operator
│   ├── Temperature
│   ├── Scattering angle
│   └── SOP / Method
│
├── Summary Metrics
│   ├── Z-average
│   ├── PDI
│   ├── Peak sizes
│   ├── Peak areas
│   └── Count rate
│
├── Distributions
│   ├── Intensity
│   ├── Volume
│   └── Number
│
├── Correlogram
│
├── Derived Metrics
│
├── AI Interpretation
│
└── Flags
```

The Measurement object should not care where the data originated.

------------------------------------------------------------------------

# Supported Inputs

LabAssistant should eventually accept:

-   Summary CSV exports
-   Pasted intensity distribution data
-   Pasted volume distribution data
-   Pasted number distribution data
-   Pasted correlogram data
-   Excel files containing copied graph data
-   Future proprietary formats if practical

Multiple inputs should merge into one Measurement.

------------------------------------------------------------------------

# Derived Metrics

LabAssistant should calculate its own metrics rather than relying only
on instrument outputs.

Examples:

-   Primary peak
-   Peak count
-   Peak symmetry
-   Peak width
-   D10
-   D50
-   D90
-   Tail area above thresholds
-   Aggregation risk
-   Distribution skewness
-   Measurement quality score
-   Correlogram noise score

These become **LabAssistant metrics**, not Zetasizer metrics.

------------------------------------------------------------------------

# Dashboard Philosophy

The dashboard should be decision-oriented.

Prioritize:

-   Measurement Health Score
-   Flagged samples
-   Best/Worst sample
-   AI findings
-   Primary distribution overlay
-   Correlogram review
-   Key metric comparisons

Hide secondary analyses inside expandable sections.

------------------------------------------------------------------------

# Long-Term Features

-   Historical experiment database
-   Trend analysis
-   Batch comparison
-   Similar experiment search
-   AI-generated reports
-   HPLC support
-   UV-Vis support
-   SEC support
-   ELISA support
-   Additional laboratory instruments

The long-term goal is to evolve from a DLS tool into a laboratory
intelligence platform.

------------------------------------------------------------------------

# Development Principles

-   Build incrementally.
-   Prefer clean architecture over quick hacks.
-   Explain architectural decisions.
-   Favor readability over cleverness.
-   Keep modules loosely coupled.
-   Do not rewrite working code unnecessarily.
-   Every feature should serve the project's vision.
-   Keep `docs/AGENT_HANDOFF.md` current so future agents can continue the
    work without rediscovering the project state.
-   When extracting architecture from `app.py`, preserve current dashboard
    behavior and add focused tests around the moved logic.

------------------------------------------------------------------------

# Immediate Roadmap

## Phase 1

Build the Measurement data model.

## Phase 2

Build flexible importers that merge multiple data sources into one
Measurement.

## Phase 3

Implement LabAssistant-derived scientific metrics.

## Phase 4

Redesign the dashboard around decision support.

## Phase 5

Add historical storage, trend analysis, and experiment comparison.

------------------------------------------------------------------------

# Current Objective

The current milestone is to make LabAssistant remember experiments.

History should be built on top of the unified `Measurement` object, not raw
uploaded files. The first implementation is local experiment history, trend
views, and a path toward comparison against previous runs.

------------------------------------------------------------------------

# Agent Continuity

Future agents should begin with:

1.  `docs/AGENT_HANDOFF.md`
2.  `docs/ARCHITECTURE.md`
3.  This roadmap
4.  `README.md`

The handoff file should always identify:

-   Current objective
-   Current project state
-   Next best move
-   Known risks
-   Validation checklist

When a milestone is completed, update the handoff file before ending the turn.
