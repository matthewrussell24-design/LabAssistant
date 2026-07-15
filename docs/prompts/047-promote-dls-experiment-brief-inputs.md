# Promote DLS Experiment Brief Inputs

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 046 - Promote Reviewed Scientific Memory Save

## Objective

Let the DLS Experiment Brief accept parsed samples directly so Streamlit does
not assemble a domain `Experiment` before requesting the immutable report
preview.

## Context

The generic `produce_experiment_brief` capability correctly accepts an
authoritative `Experiment`, but Streamlit is the final UI caller of
`dls_experiment_from_samples`. The application layer can provide a narrow DLS
composition without weakening established Experiment-first callers.

## Tasks

- Extend `produce_experiment_brief` to accept an `Experiment` or non-empty
  parsed DLS samples.
- Preserve authoritative `Experiment` behavior and immutable output.
- Assemble parsed DLS samples with the established observation generation and
  current Streamlit label.
- Add empty and malformed parsed-sample validation.
- Remove Streamlit's import and call of `dls_experiment_from_samples`.
- Add compatibility, identity, observation, immutability, and validation tests.

## Deliverables

- Parsed-DLS input support for `produce_experiment_brief`.
- Streamlit Experiment Brief migration.
- Updated application capability documentation and handoff.

## Success Criteria

Streamlit requests the DLS Experiment Brief from parsed samples through the
application layer without importing or calling `dls_experiment_from_samples`,
while generic `Experiment` callers retain existing behavior.

## Implementation Summary

- Extended the existing generic brief capability with a narrow parsed-DLS input
  path while leaving authoritative `Experiment` behavior unchanged.
- Reused `dls_experiment_from_samples` inside the application layer so the DLS
  label, normalized observations, identity fields, investigation, five report
  sections, and immutable serialization retain established behavior.
- Added explicit empty and malformed parsed-sample errors plus compatibility
  coverage for DLS identity, observation categories, observation evidence, and
  section ordering.
- Migrated Streamlit to submit parsed samples and removed its final import and
  call of `dls_experiment_from_samples`.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/047-promote-dls-experiment-brief-inputs.md`

## Test Results

- Focused Experiment Brief tests: 4 passed.
- Full suite: 220 passed in 2.59s.
- Headless Streamlit startup and health smoke passed on port 8765.

## Remaining Work

- Promote the qualified filtration relationship hypothesis out of Streamlit's
  static callout and into an evidence-aware immutable application read.
