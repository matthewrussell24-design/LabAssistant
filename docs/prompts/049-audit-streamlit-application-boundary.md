# Audit The Streamlit Application Boundary

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 048 - Promote Filtration Relationship Hypothesis

## Objective

Audit every direct `app.py` dependency outside `labassistant.application`,
remove dead boundary leaks, and decide whether the Application Layer Extraction
milestone is complete for the current human workflows.

## Context

The active experiment assembly, persistence, scientific reads, and reviewed
evidence commands now cross application contracts. The remaining direct core
imports appear to support presentation formatting, visualization thresholds,
widget/input handling, and transitional DLS workspace state, but that boundary
needs an explicit evidence-backed classification before the extraction
milestone can close.

## Tasks

- Inventory every non-application `labassistant` import in `app.py` and inspect
  its call sites.
- Classify dependencies as presentation, visualization, input handling,
  reviewed command data, transitional UI state, or an application-boundary gap.
- Remove imports or type references that no longer have a runtime caller.
- Record intentional UI ownership and any remaining architectural risk.
- Decide whether the extraction milestone is complete without equating workflow
  extraction with a fully mature, transport-neutral application layer.

## Deliverables

- A concise boundary inventory in the architecture capability record.
- Removal of dead Streamlit-to-core dependencies.
- An evidence-based milestone decision and clearly scoped next task.

## Success Criteria

Every direct core dependency in `app.py` has an explicit reason to remain, no
dead domain type widens the UI boundary, and the project handoff distinguishes
completed workflow extraction from remaining contract-maturity work.

## Implementation Summary

- Classified all remaining direct core imports as presentation formatting and
  thresholds, widget/input handling, reviewed command data, or transitional UI
  workspace typing.
- Removed the obsolete `RelationshipAnalysis` import and renderer union branch;
  every relationship renderer caller now uses immutable application summaries.
- Confirmed that workflow orchestration, persistence, and scientific claim
  construction cross application contracts for current human workflows.
- Closed the Application Layer Extraction milestone while retaining the broader
  Mature Application Layer platform item as incomplete because application
  internals still depend on DLS view-model helpers and transitional
  `ParsedSample` inputs.

## Files Changed

- `app.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/049-audit-streamlit-application-boundary.md`

## Test Results

- Full suite: 224 passed in 2.73s.
- Headless Streamlit startup and health smoke passed on port 8765.
- `git diff --check` passed.
- `graphify update .` rebuilt the code graph successfully.

## Remaining Work

- Define a presentation-neutral DLS evidence contract and migrate application
  paths away from direct `labassistant.view_models` coupling while preserving
  compatibility adapters for current shells.
