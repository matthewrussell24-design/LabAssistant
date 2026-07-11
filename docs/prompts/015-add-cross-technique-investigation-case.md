# Add A Cross-Technique Investigation Case

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 014 - Generalize Persisted Restoration For Chromatography

## Objective

Prove end-to-end reasoning across chromatography missing mass, DLS aggregation
evidence, and filtration outcomes using normalized, traceable observations.

## Context

The three evidence types are modeled, and chromatography can already combine
missing-mass and DLS observations into a qualified hypothesis. Filtration
follow-up lacks a normalized observation adapter, so it cannot yet participate
in the same experiment-level investigation stream.

## Tasks

- Normalize elevated filtration difficulty and observed clogging into observations.
- Preserve source and sample provenance in each observation.
- Extend mass-balance hypothesis combination with optional filtration evidence.
- Add one representative experiment-level integration test.
- Ensure wording expresses association, not causation.

## Deliverables

- Filtration observation generation.
- A qualified three-technique hypothesis.
- A deterministic cross-technique Investigator test and aligned documentation.

## Success Criteria

One experiment combines evidence from all three techniques, produces a
traceable and appropriately qualified missing-mass hypothesis, and remains
interpretable through the instrument-independent Investigator.

## Implementation Summary

- Added filtration observation generation for elevated difficulty and recorded
  clogging, with sample and source provenance plus cautious recommendations.
- Extended mass-balance hypothesis combination with optional filtration
  evidence while retaining the existing DLS/chromatography hypothesis.
- Added an experiment-level integration case that passes observations from all
  three techniques through the unchanged, instrument-independent Investigator.
- Protected scientific wording by asserting association rather than causation.

## Files Changed

- `labassistant/filtration.py`
- `labassistant/chromatography.py`
- `tests/test_filtration.py`
- `tests/test_cross_technique_investigation.py`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/status/current-state.md`
- `docs/prompts/015-add-cross-technique-investigation-case.md`

## Test Results

- Focused filtration, chromatography, Investigator, and integration tests: 16 passed.
- Full suite: 153 passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote experiment investigation into a versioned application read contract
  when routing the first human shell through it.
