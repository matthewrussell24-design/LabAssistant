# Isolate DLS Raw Evidence Adapter

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 055 - Project DLS Distributions From Measurements

## Objective

Isolate raw DLS table inspection behind a narrow structural adapter contract,
without forcing opaque vendor tables into the normalized Measurement model.

## Context

All normalized DLS application workflows are Measurement-first. Raw inspection
is intentionally different: scientists need original vendor columns, metadata,
source text, and classified-file diagnostics exactly as imported.

## Tasks

- Define explicit raw table, sample, group, and file diagnostic protocols.
- Accept those protocols in `retrieve_dls_raw_evidence` instead of the broader
  scientific sample contract.
- Preserve arbitrary cells, column and row order, metadata order, complete
  source text, grouped file order, and immutable output.
- Prove a minimal non-Measurement adapter can use the capability.
- Audit and document whether this closes Application Contract Stabilization.

## Success Criteria

Raw inspection has a bounded adapter input, normalized application workflows
remain Measurement-first, existing raw evidence behavior is unchanged, and the
application-layer maturity boundary is stated explicitly.

## Implementation Summary

- Added structural protocols for opaque raw tables, samples, upload groups, and
  classified file diagnostics.
- Narrowed raw retrieval without requiring Measurement or the broader DLS
  scientific evidence contract.
- Preserved vendor cells, ordering, metadata, source text, diagnostics, and
  immutable outputs; added a minimal non-Measurement adapter regression.
- Removed one residual workspace-warning read found by the closing audit.
- Closed Application Contract Stabilization for current human workflows.

## Files Changed

- `labassistant/dls_evidence.py`
- `labassistant/application.py`
- `tests/test_application.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/056-isolate-dls-raw-evidence-adapter.md`

## Test Results

- Focused raw-evidence coverage: 3 passed.
- Full suite: 233 passed in 2.89s.

## Remaining Work

- Contract versioning and API-readiness hardening are the next milestone; no
  further workspace-to-Measurement migration is planned.
