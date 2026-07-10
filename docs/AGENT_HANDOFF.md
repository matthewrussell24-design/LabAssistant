# Agent Handoff

This file orients a new agent to LabAssistant's direction and the current best
next move. It is a companion to the canonical status page, not a replacement.

**Read `docs/status/current-state.md` first.** It is the authoritative,
five-minute project handoff and part of the definition of done for substantial
work. This file adds durable context and rationale that the status page keeps
deliberately short. When the two disagree, `current-state.md` wins and this file
should be corrected.

## Current Objective

LabAssistant is a standalone **Experiment Intelligence** application that turns
laboratory data into trustworthy scientific findings and practical next steps.
It is not a DLS analyzer, a Zetasizer dashboard, or a Streamlit tool. Streamlit
is the first human-facing shell; a native macOS desktop shell is the second. The
Zetasizer/DLS workflow is the first supported use case and must stay stable
while the core grows toward experiment-first ingestion, reasoning, memory, and
reporting.

Guiding frame:

```text
The intelligence layer is the product. Instruments are plugins.
Experiments are first-class objects. Measurements are building blocks.
```

Every experiment should answer four questions: what happened, is it trustworthy,
why does it matter, and what to do next. Human scientists are the first users;
future agents are planned clients of the same application core, starting with
stable read-only contracts and reviewed commands later. Do not add speculative
agent runtimes, remote APIs, autonomous lab actions, or instrument control
before the human app and application-service layer are stable.

## Architecture In One Screen

```text
UI shells (Streamlit app.py  +  native desktop labassistant.desktop)
  -> application boundary (labassistant.application: capabilities + read models)
  -> scientific core (models, metrics, quality, aggregation, trend, investigator)
  -> instrument importers (DLS, filtration, chromatography CSV, OpenLab .olax)
  -> local persistence + scientific memory (history JSONL, context engine)
```

- `labassistant.application` is the explicit boundary both shells depend on. It
  exposes a **transport-independent capability registry** (currently nine stable
  names) plus versioned read models (`ExperimentSnapshot`, `DLSAnalysisResult`,
  `RetrievedExperiment`, `ExperimentListing`). Interfaces should call a
  capability when one exists instead of constructing or mutating domain models.
- `Experiment` is the instrument-agnostic reasoning unit; `Observation` is the
  normalized finding; `Measurement`/`ChromatographyMeasurement` are evidence.
- The Scientific Investigator (`investigator.py`) reasons over Observations
  only — never raw files — so any importer that emits Observations is
  interpretable by the same engine.
- Persistence is local JSONL history plus a knowledge/context store. Interface
  shells must not read JSONL directly; they go through application queries.

Canonical detail lives in `docs/VISION.md`, `docs/ARCHITECTURE.md`,
`docs/ROADMAP.md`, `docs/STANDALONE_APP.md`, and
`docs/architecture/capabilities.md`.

## Where We Are

Working and tested today:

- **DLS/Zetasizer** — multi-file lot import, canonical backscatter-based
  distribution metrics with provenance, dual-angle aggregation screening,
  quality/reproducibility/drift/trend analysis, decision-first Streamlit
  dashboard, JSONL history with append-only rehydration, comparison, and
  similar-run search.
- **Filtration** follow-up (ordinal difficulty rubric, Spearman correlations) as
  orthogonal cross-technique evidence stored on DLS measurements.
- **Chromatography / mass balance** — models plus Agilent OpenLab `.olax`
  ingestion that *locates* evidence and emits Observations. Detector-signal
  decoding and peak-table parsing are not implemented yet (see ROADMAP Phase 9).
- **Two shells** — the Streamlit app and a native AppKit/WebKit desktop research
  workspace. Qt was removed after repeated Cocoa plugin failures; the desktop
  pins PyObjC and uses AppKit directly.
- **Application layer** — nine capabilities: `describe_platform`,
  `describe_agent_access`, `import_dls_experiment`, `analyze_dls_dataset`,
  `import_chromatography_experiment`, `list_experiments`, `retrieve_experiment`,
  `retrieve_experiment_summary`, `save_scientific_memory`. The desktop History
  timeline browses and restores persisted records through the boundary
  (`list_experiments` + the `restore_dls_experiment` composition over
  `retrieve_experiment`).

Most recently completed: **task 010** — promoted persisted experiment listing
into the application layer and wired the desktop timeline plus "Open Existing
Experiment" to browse and restore saved records. See
`docs/prompts/010-promote-persisted-experiment-listing.md`.

## Next Best Move

Keep the current-state page authoritative, but the near-term direction is:

1. **Promote experiment comparison** into the application layer — a versioned
   `compare_experiments` capability over the existing
   `labassistant.history.compare_experiments`/`compare_to_history` drift logic,
   with at least one shell caller. This is the current "Next Recommended Task"
   in `current-state.md`. It lets a scientist see how a current or restored
   experiment differs from prior saved runs without any UI owning the math.
2. **Generalize restore** beyond the DLS read model once a second persisted
   technique exists.
3. **Decode chromatography** (ROADMAP Phase 9): parse detector signals and peak
   tables into `ChromatographyPeak`/traces, wire quantitation into the
   mass-balance engine, and extend the Investigator with technique-aware checks.
4. **Cross-technique reasoning**: link HPLC "missing mass" to DLS aggregation
   Observations (the hypothesis link already exists) toward true mass-balance
   investigation.
5. **A second instrument adapter** (SEC or UV-Vis) against the same
   Experiment/Observation contract to prove the architecture generalizes.
6. **Desktop packaging** — notarization and multi-display QA — kept separate
   from scientific capability work.

Promote one capability or adapter at a time, with typed inputs, versioned read
outputs, validation, and focused compatibility tests, only when a real human
workflow becomes its first caller. The candidate capability backlog lives in
`docs/architecture/capabilities.md`.

## Guardrails And Non-Goals

- Preserve the working Zetasizer workflow and the human app workflow while
  extracting boundaries. Refactors are compatibility-first and incremental.
- Keep instrument parsing instrument-specific and scientific reasoning
  instrument-independent.
- Reports and analysis describe experiments, not datasets. Do not let
  presentation code invent causes or conclusions absent from the read model.
- Until the application layer is mature, do not introduce an HTTP service,
  microservices, an autonomous agent runtime, or an instrument-control path;
  do not migrate away from Streamlit or replace JSONL persistence. Revisit a
  non-goal only through a scoped prompt with architecture rationale.

## Durable Facts Worth Keeping

- Lot normalization: `446-01`, `Lot 446-01`, `Lyo 446-01`, and `Lot 1` all
  normalize to `lot_1` and display as `Lot 1`.
- Dual-angle aggregation detection (Malvern AN101104 / AN140527) is a headline
  scientific feature, not a minor metric; index is
  `Z_forward / Z_backscatter - 1`, treated as corroborating evidence, never
  proof. Full design detail is in this file's git history and
  `docs/ARCHITECTURE.md`.
- Trimmed Lot 1 fixtures under `tests/fixtures/` lock in real-export behavior;
  do not delete them. Validate parser changes with synthetic and representative
  real files, and add regression tests before changing classifier/lot heuristics.
- Local history stores full `Measurement.to_dict()` payloads as JSONL; treat it
  as an early schema and add migration care before changing keys.
- `.labassistant_history/`, `graphify-out/`, and `.venv/` are gitignored.

## Working Rules For Agents

- Read `docs/status/current-state.md`, then the relevant prompt in
  `docs/prompts/` and any architecture/decision record it links, before
  substantial work.
- Check `git status --short` first and preserve unrelated or previous-agent
  changes. Keep changes scoped to the current milestone.
- Prefer extracting pure, tested logic over redesigning the UI. Add or update
  tests in the same change whenever practical.
- Call an application capability when one exists instead of touching domain
  models or storage from a shell.
- Update `current-state.md` (and this file when the direction changes) before
  declaring substantial work complete, run `graphify update .`, and keep
  status-page links and `AGENTS.md` accurate.
- Do not push unless the user explicitly requests it.

## Validation Checklist

Before handing off:

- Run `scripts/test -q` (or `.venv/bin/python -m pytest -q`).
- If UI behavior changed, smoke test the affected shell.
- Confirm imports work from a clean Python process.
- Update `current-state.md` and this file if the next best move changed.
- Leave `git status --short` understandable.
