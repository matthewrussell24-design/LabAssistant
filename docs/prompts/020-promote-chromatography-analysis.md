# Promote Chromatography And OpenLab Analysis

Status: Complete
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: 019 - Promote Standalone Scientific Note Creation

## Objective

Move chromatography CSV and OpenLab `.olax` import-analysis orchestration from
Streamlit into one typed, toolkit-independent application workflow.

## Tasks

- Select the supported importer by source suffix inside the application layer.
- Preserve CSV mass-balance assessment, trends, observations, and hypotheses.
- Preserve OpenLab injection summaries, archive counts, observations, and limitations.
- Return immutable read models without pandas DataFrames or mutable measurements.
- Preserve explicit memory saving through copy-on-access experiment restoration.
- Register the capability, migrate Streamlit, and test both source formats and errors.

## Success Criteria

Streamlit renders and saves chromatography/OpenLab analysis from a typed
application result without directly orchestrating importers or hypotheses.

## Implementation Summary

- Added a unified `analyze_chromatography_source` workflow that selects CSV or
  OpenLab ingestion by suffix and owns temporary uploaded-archive handling.
- Added frozen assessment, trend, archive-summary, injection, observation, and
  analysis read models without pandas or mutable measurement exposure.
- Preserved CSV mass-balance calculations, trends, observations, hypotheses,
  and the existing OpenLab injection/archive/limitation behavior.
- Added copy-on-access experiment restoration for explicit memory saves.
- Registered the workflow without Agent access and routed Streamlit through it.

## Files Changed

- `labassistant/application.py`
- `app.py`
- `tests/test_application.py`
- `tests/test_memory_app_integration.py`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/020-promote-chromatography-analysis.md`

## Test Results

- Focused application, memory integration, chromatography, and OpenLab tests: 46 passed.
- Full suite: 164 passed in 2.44s.
- Headless Streamlit startup smoke passed.
- `git diff --check`, status-page link verification, and graph update passed.

## Remaining Work

- Promote filtration CSV import and follow-up summaries into a typed application
  workflow so Streamlit no longer orchestrates that importer directly.
