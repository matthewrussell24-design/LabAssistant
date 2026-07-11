# Promote Normalized Observation Generation

Status: Complete
Created: 2026-07-11
Last Updated: 2026-07-11
Priority: High
Depends On: 022 - Promote Persisted Experiment Saving

## Objective

Promote normalized finding generation for supported scientific evidence into a
typed, immutable application workflow.

## Context

DLS and chromatography application workflows coordinated domain observation
helpers independently. Filtration exposed the same normalized finding concept
without a shared application contract.

## Tasks

- Define a technique-aware entry point for DLS, chromatography, and filtration evidence.
- Preserve importer- and domain-owned scientific rules rather than reimplementing them.
- Return immutable observation summaries with full evidence provenance.
- Provide fresh domain observations only for internal experiment assembly.
- Register the workflow and route existing DLS and chromatography application paths through it.

## Deliverables

- `generate_observations` capability.
- Frozen `ObservationRead` and `ObservationGenerationResult` contracts.
- Validation and compatibility coverage for all three supported techniques.

## Success Criteria

Supported application workflows request normalized findings through one
registered capability without coordinating technique helpers independently,
while existing DLS and chromatography results remain compatible.

## Implementation Summary

- Added a technique-aware observation workflow supporting DLS parsed samples,
  chromatography measurements plus mass-balance assessment, and filtration measurements.
- Added immutable observation read models and copy-on-access domain restoration.
- Preserved authoritative domain rules, including fresh chromatography assessment findings.
- Routed DLS experiment assembly, chromatography restore, and chromatography CSV
  analysis through the shared workflow.
- Registered the capability for Human UI, Agent, CLI, and Future API callers.

## Files Changed

- `labassistant/application.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/023-promote-observation-generation.md`

## Test Results

- Focused application, observation, chromatography, and filtration tests: 55 passed.
- Full suite: 171 passed in 2.49s.

## Remaining Work

- Promote experiment-level brief/report generation behind an application contract.
