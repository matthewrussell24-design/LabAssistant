# LabAssistant Current State

**Project:** LabAssistant
**Version:** 0.1.0-dev
**Repository Root:** `LabAssistant/`
**Primary Branch:** `main`
**Architecture Version:** 2

## Repository State

- Current Branch: `main`
- Latest Completed Change: Added scoped local read policy and bounded candidate
  collection responses (task 059).
- Working Tree: Task 059 is committed locally; inspect `git status --short`
  before beginning new work.
- Last Successful Test: `237 passed in 2.58s` from `scripts/test -q` on
  2026-07-15.
- Supported Python Version: Python 3.12; last verified with Python 3.12.13.
- Last Updated: 2026-07-15 for task 059.

## North Star

LabAssistant succeeds when a scientist can move from raw experimental data to a
well-supported scientific conclusion faster, with greater confidence, and with
full traceability.

## Project Health

- Architecture: 🟢 Healthy — target boundaries and migration direction are
  documented.
- Tests: 🟢 Healthy — 237 passing.
- Documentation: 🟢 Current — canonical status, navigation, prompts, and
  decisions are aligned.
- Application Layer: 🟢 Mature for current workflows — normalized DLS reads are
  Measurement-first, raw vendor inspection is explicitly adapter-bounded, and
  reusable human workflows cross typed application contracts.
- API Layer: 🟡 Foundation — seven candidates share draft JSON envelopes,
  scoped local access policy, and bounded collections; final version freeze and
  transport remain absent.
- Agent SDK: ⚪ Planned — read-only application contracts come first.

Health labels summarize the evidence in the detailed sections below. Update a
label only when that evidence changes; do not use green to hide a known risk or
use planned work to imply an active implementation commitment.

## Platform Progress

- ✅ Documentation workflow
- ✅ Living status page
- ✅ Experiment model
- ✅ Observation model
- ✅ Initial application boundary
- ✅ Capability catalog and registry
- ✅ Mature application layer
- ⬜ API layer
- ⬜ Agent SDK
- ⬜ Authentication
- ✅ Desktop prototype
- ✅ Polished desktop workspace
- ⬜ Packaged desktop application
- ⬜ Deployment

Checked items are present and tested, not necessarily final. Unchecked items
are future platform capabilities and are not automatically the next task.

## Current Milestone

- Milestone: API Contract Readiness
- Status: In Progress
- Goal: Freeze a small, versioned, read-only external surface without exposing
  Python-only domain/workspace inputs or prematurely choosing a transport.
- Current evidence: Task 057 audited all 42 registry entries, selected seven
  candidate reads, defined draft-to-stable versioning, and recorded a no-go for
  HTTP or agent transports until shared envelopes, stable errors, access
  boundaries, limits, and JSON conformance tests exist. Task 058 completed the
  envelopes, errors, safe invocation, and conformance tests without changing
  existing handlers. Task 059 added policy-derived local access and honest
  bounds/pagination metadata for every candidate collection.

## Five-Minute Rule

Every important project document should reveal its purpose within five minutes:

- This document answers: Where are we?
- `docs/ROADMAP.md` answers: Where are we going?
- `docs/ARCHITECTURE.md` answers: Why is it built this way?
- `AGENTS.md` answers: How should an AI work here?
- `docs/prompts/*.md` answers: What should be implemented next?

Prefer clear entry points, scoped detail, and links to deeper records over
duplicating history in multiple documents.

This page is the operating system for project coordination. The README routes
contributors here; this page routes them to the relevant roadmap, architecture,
prompt, decision, and standard records before implementation begins.

## Project Vision

LabAssistant is a human-first, standalone Experiment Intelligence application
for turning laboratory data into trustworthy scientific findings and practical
next steps. DLS/Zetasizer is the mature first workflow; chromatography and
filtration are the first steps toward a broader platform.

## Long-Term Vision

LabAssistant should become a standalone, agent-native scientific reasoning
platform with a human-first interface. Its instrument-independent core should
serve application shells and a stable API while preserving provenance,
trustworthy evidence, and human control.

## Current Architecture

The current data and control flow is:

```text
Streamlit UI (`app.py`) or native prototype (`labassistant.desktop`)
  -> application boundary and view models/read models
  -> instrument importers and experiment assembly
  -> Measurement / Experiment / Observation models
  -> metrics, quality, aggregation, trend, and investigator reasoning
  -> local history and knowledge/context storage
```

- `app.py` owns UI layout, widgets, session state, and visualization.
- Its remaining direct core imports are limited to display formatting and
  thresholds, widget/input normalization, a reviewed filtration command DTO,
  and transitional `ParsedSample` workspace typing. The dependency inventory
  is recorded in `docs/architecture/capabilities.md`.
- `labassistant.dls_evidence` owns the structural DLS sample protocol, mutable
  local workspace adapter, frozen Measurement metrics/status projection, and
  compatibility tables. `ParsedSample` remains an alias exposed by
  `labassistant.view_models`; reusable core modules no longer import that
  presentation facade.
- `labassistant.desktop` owns native startup and application invocation;
  `labassistant.ui` owns the pure presenter, local workspace document, and
  AppKit/WebKit controller.
- `labassistant.application` exposes app and agent-access policy, read-only
  experiment snapshots, DLS/chromatography assembly, knowledge persistence, and
  persisted experiment retrieval, listing, summary/trend history views,
  technique-aware DLS and chromatography restoration, local DLS and
  chromatography/OpenLab analysis, immutable investigation results,
  scientific-context and Research Journal reads, and a transport-independent
  registry of forty-two stable capability names, including explicit
  human/CLI-only note, experiment-history, and reviewed-evidence commands.
- Importers translate DLS, filtration, chromatography CSV, and OpenLab `.olax`
  sources into domain evidence.
- `Measurement` and `ChromatographyMeasurement` hold instrument evidence.
  `Experiment` is the instrument-agnostic reasoning unit, and `Observation` is
  the normalized finding shared by reasoning layers.
- Deterministic analysis lives outside the UI in metrics, quality, aggregation,
  trend analysis, chromatography, observations, and the Scientific
  Investigator.
- Persistence is local. Experiment history uses JSONL; the context engine
  manages reusable scientific knowledge and memory.

The intended boundary is UI shells -> application services -> scientific core.
Future agent access begins with versioned, read-only application contracts. An
HTTP service, autonomous agent runtime, and instrument control are current
non-goals.

## Important Decisions

- The repository is the source of truth. Substantial requests and completion
  records live together in `docs/prompts/`.
- This page is the primary handoff and part of the definition of done for
  substantial work.
- LabAssistant is a standalone experiment-intelligence product; Streamlit is a
  replaceable current shell.
- Human workflows come first. Future agents receive stable read-only contracts
  before reviewed write commands.
- Experiments are the top-level reasoning unit, measurements are evidence, and
  normalized observations connect instrument adapters to shared reasoning.
- Refactors are compatibility-first and incremental. Preserve the mature DLS
  workflow while extracting stable boundaries.
- Instrument parsing stays instrument-specific; scientific reasoning operates
  on normalized, reusable evidence.

## Recent Decisions

2026-07-15:

- Registry availability does not imply external API stability or authorization.
- The first freeze candidate is limited to seven read operations.
- External contracts require common success/error envelopes, stable error codes,
  bounded reads, access policy, and JSON conformance before transport selection.
- `0.1-draft` remains in place until that hardening gate passes.

2026-07-10:

- Streamlit is a replaceable UI shell, not the product boundary.
- The first explicit application boundary and read-only experiment snapshot
  contract were introduced.
- This status page became the primary project handoff and AI coordination
  document.
- Future APIs should target the application layer instead of exposing domain
  models directly.
- Human interfaces, future APIs, CLIs, and agents should share capability names
  based on scientific intent rather than low-level functions.

This is a concise captain's log, not a replacement for formal decision records.
Keep only the most recent strategic choices here and preserve full rationale in
`docs/decisions/`.

## Architect's Notes

- Favor incremental, compatibility-first refactors over sweeping rewrites.
- Optimize human scientific workflows before autonomous-agent workflows.
- Every reusable capability should eventually be callable through the
  application layer.
- Keep scientific reasoning independent of instrument type.
- Keep instruments as adapters and experiments as the unit of scientific
  meaning.

These notes guide near-term judgment but do not replace architecture records
when a decision establishes a durable contract.

## Current Non-Goals

Until an explicitly scoped next-milestone prompt changes direction, do not:

- Introduce FastAPI or another HTTP service.
- Split the application into microservices.
- Migrate away from Streamlit.
- Replace JSONL persistence.
- Redesign the compatible Streamlit UI or add scientific behavior in
  presentation code.
- Add an autonomous agent runtime or instrument-control path.

Revisit a non-goal only through an explicitly scoped prompt with supporting
architecture rationale.

## Repository Structure

- `app.py` — current Streamlit application shell.
- `labassistant/desktop.py` — native desktop startup/controller entry point.
- `labassistant/ui/` — reusable presentation helpers, self-contained workspace
  document, and native AppKit/WebKit controller.
- `labassistant/` — reusable application and scientific core.
- `labassistant/application.py` — app-level contracts, capability registry, and
  experiment assembly.
- `labassistant/models.py` — measurements, experiments, observations,
  chromatography, and investigator result models.
- `labassistant/importers/` — DLS, filtration, chromatography, and OpenLab
  ingestion.
- `labassistant/metrics.py`, `quality.py`, `aggregation.py`, and
  `trend_analysis.py` — DLS and shared quantitative analysis.
- `labassistant/chromatography.py`, `filtration.py`, and `observations.py` —
  technique models and normalized finding generation.
- `labassistant/investigator.py` — deterministic, instrument-independent
  reasoning over observations.
- `labassistant/history.py` and `context_engine.py` — local history and
  scientific memory.
- `labassistant/measurements.py` and `dls_evidence.py` — DLS measurement and
  structural workspace-evidence adapters; `view_models.py` preserves legacy UI
  imports and `interpretation.py` owns presentation-ready summaries.
- `tests/` — unit, integration, importer, and representative-fixture coverage.
- `docs/` — status, prompts, architecture, roadmap, standards, decisions,
  vision, and technical proposals.
- `graphify-out/` — generated knowledge graph and architecture navigation data.
- `scripts/` — repository run and test entry points.

## Recently Completed Work

- Established the repository documentation workflow with numbered prompts,
  indexes, standards, and decision records (task 001).
- Established this living status page as the primary implementation-session
  handoff (task 002).
- Refined the status page into the canonical five-minute onboarding document
  and aligned permanent agent guidance (task 003).
- Defined the transport-independent capability layer, documented its backlog,
  and added a tested registry for six existing operations (task 004).
- Promoted persisted experiment retrieval into the capability layer and routed
  the Streamlit saved-experiment loader through it (task 005).
- Canonicalized lot-level DLS distribution metrics on averaged backscatter
  evidence, with explicit single-angle, replicate-average, and legacy
  intensity fallbacks plus source provenance (task 006).
- Added synthetic DLS format regressions for decimal-comma delimiters,
  single-angle summaries, and explicit rejection of volume/number-only files
  as intensity evidence (task 007).
- Added a native desktop vertical slice and typed local DLS analysis
  capability, proving the core can serve a native shell without importing
  Streamlit (task 008).
- Replaced the prototype text view with a polished, modular research workspace
  using reusable cards, metric tiles, semantic status, structured analysis,
  purposeful empty states, and clickable session history (task 009).
- Promoted persisted experiment listing into the application layer with a
  versioned, metadata-only `list_experiments` query and a `restore_dls_experiment`
  composition over `retrieve_experiment`; wired the desktop History timeline and
  "Open Existing Experiment" to browse and restore persisted records without the
  UI reading JSONL storage (task 010).
- Promoted immutable experiment comparison and related-experiment search into
  the application layer and routed both Streamlit workflows through the shared
  contracts (tasks 011 and 012).
- Promoted history summary and trend retrieval into an immutable application
  read contract and routed the Streamlit History panel through it (task 013).
- Generalized persisted restoration for chromatography with nested evidence
  reconstruction and an immutable application read result (task 014).
- Added normalized filtration observations and proved a qualified three-technique
  investigation path without adding instrument logic to the Investigator (task 015).
- Promoted experiment investigation into an immutable application read contract
  and routed the Streamlit Experiment Brief through it (task 016).
- Promoted related scientific-context retrieval into an immutable application
  read contract and routed the Streamlit memory panel through it (task 017).
- Promoted Research Journal reads and Markdown export into an immutable
  application contract and routed Streamlit through it (task 018).
- Promoted standalone scientific-note creation into a validated application
  command with immutable receipt metadata (task 019).
- Promoted chromatography CSV and OpenLab import-analysis into a typed
  application workflow and routed Streamlit through it (task 020).
- Promoted filtration CSV import into immutable application summaries while
  retaining explicit user-reviewed DLS attachment (task 021).
- Promoted persisted experiment saving into a validated human/CLI-only command
  that returns immutable receipt metadata (task 022).
- Promoted normalized DLS, chromatography, and filtration observation generation
  into one typed immutable application workflow (task 023).
- Promoted the generic Experiment Brief into an immutable Experiment-first report
  preview and routed Streamlit through it (task 024).
- Promoted uploaded multi-file DLS preview and import orchestration into an
  immutable application result and routed Streamlit through it (task 025).
- Promoted DLS-specific decision ranking into immutable attention rows and
  routed Streamlit's Decision Brief through it (task 026).
- Promoted DLS automated findings and trend-story composition into ordered,
  immutable narrative sections and routed both Streamlit views through one
  application result (task 027).
- Added detailed DLS diagnostic analysis to the same immutable narrative result
  and removed Streamlit's final direct narrative-builder call (task 028).
- Promoted the DLS screening score, warning counts, and medians into an
  immutable, pandas-free health overview and routed Streamlit through it (task 029).
- Promoted DLS control-chart and replicate-statistics tables into typed,
  immutable rows and routed both Streamlit diagnostics through one result (task 030).
- Promoted reviewed circulation-time versus forward-angle DLS analysis into
  immutable points and qualified relationship summaries (task 031).
- Promoted filtration difficulty versus DLS/circulation trend analysis into
  immutable points and three qualified Spearman summaries (task 032).
- Promoted dual-angle aggregation screening into nested immutable angle evidence,
  checklist items, and available/unavailable sample assessments (task 033).
- Promoted per-sample status, warning evidence, and ordered scientific display
  values into immutable presentation-neutral summaries (task 034).
- Promoted per-angle DLS detail into immutable typed rows with preserved sample
  and angle ordering plus empty-angle behavior (task 035).
- Promoted the shared DLS metrics projection into immutable typed rows and kept
  pandas reconstruction in the Streamlit shell (task 036).
- Promoted DLS distribution-series evidence into immutable typed samples,
  signals, points, and peaks while keeping chart state in Streamlit (task 037).
- Promoted raw DLS point tables, metadata, and source diagnostics into immutable
  application reads while keeping display and export in Streamlit (task 038).
- Promoted DLS correlogram traces and noise scores into immutable application
  series while keeping diagnostic chart composition in Streamlit (task 039).
- Promoted paired-angle forward/back distribution curves into immutable
  application evidence while keeping selection and Plotly composition in
  Streamlit (task 040).
- Extended immutable history comparison and related-run capabilities to accept
  parsed DLS samples directly while retaining measurement compatibility and UI
  selection state (task 041).
- Extended the reviewed experiment-history save command to resolve parsed DLS
  samples internally while preserving generic serializable evidence, defensive
  copying, and append-only lineage (task 042).
- Promoted reviewed circulation-time reads and mutation into explicit
  parsed-sample contracts while keeping session state and blank-input decisions
  in Streamlit (task 043).
- Promoted reviewed filtration retrieval, single-sample mutation, and ordered
  CSV attachment into parsed-sample contracts while keeping widgets, pressure
  normalization, prefill, and feedback in Streamlit (task 044).
- Migrated saved DLS workspace restoration into a technique-aware,
  copy-on-access application workflow while keeping the native analysis result
  read-only and preserving Streamlit session behavior (task 045).
- Promoted reviewed DLS and chromatography scientific-memory saves into a
  mutation-safe application command with immutable receipts while keeping
  selection, labels, project tags, notes, and confirmation in Streamlit (task 046).
- Extended the immutable generic Experiment Brief with parsed-DLS inputs and
  removed Streamlit's final direct DLS experiment assembly while preserving
  authoritative `Experiment` callers (task 047).
- Promoted the filtration relationship hypothesis into an immutable read that
  preserves insufficient, partial, and fully qualified evidence states with
  explicit non-causal language (task 048).
- Audited the remaining Streamlit-to-core imports, removed a dead domain type,
  and closed current-workflow application extraction (task 049).
- Introduced the structural `DLSSampleEvidence` contract and retained
  `ParsedSample` as a compatibility alias without reusable-core view-model
  imports (task 050).
- Routed the immutable application metrics read and compatibility dataframe
  through a frozen Measurement-first metrics/status projection (task 051).
- Routed ordered review evidence and immutable per-sample display summaries
  through the Measurement-first projection (task 052).
- Routed attention scoring, warning rows, and narrative distribution-confidence
  checks through Measurement evidence (task 053).
- Routed DLS warning iteration, observation evidence, status severity, and
  correlogram findings through Measurement flags and projected metrics (task 054).
- Routed immutable DLS distribution selection, signals, points, and peaks
  through authoritative Measurement distributions (task 055).
- Bounded raw DLS inspection behind structural adapter protocols and closed the
  current-workflow application stabilization milestone (task 056).
- Classified all 42 registered capabilities, selected seven candidate reads,
  and established API contract-freeze/versioning policy (task 057).
- Added draft success/error envelopes, safe candidate-read invocation, and JSON
  conformance coverage while preserving existing handlers (task 058).
- Added scoped local read policy and deterministic collection bounds without
  treating loopback as identity or adding remote authentication (task 059).
- Added the first explicit application boundary and versioned, read-only
  `ExperimentSnapshot`.
- Added DLS and chromatography experiment assembly.
- Added instrument-independent `Experiment` and `Observation` models and the
  Scientific Investigator reasoning layer.
- Added OpenLab `.olax` ingestion, chromatogram trace decoding,
  chromatography/mass-balance models, and normalized observations.
- Added filtration follow-up measurements and persisted circulation variables
  for cross-technique investigation.
- Preserved the working DLS workflow: multi-file lot import, derived metrics,
  dual-angle aggregation assessment, decision-first UI, history, comparison,
  trends, and similar-run search.

## Active Work

- Local read-policy and bounded-collection task 059 is complete.
- The working tree was clean when task 059 began.

## Known Risks

- Package boundaries remain partly DLS-shaped, increasing coupling during
  future extraction into application, ingestion, metrics, and reasoning areas.
- Parser validation does not yet cover enough vendor versions, locales,
  delimiters, workbook layouts, distribution types, or real OpenLab archives.
- JSONL history has limited migration and query support; schema evolution needs
  care until stronger persistence requirements justify a change.
- `requirements.txt` is unpinned, so environment resolution is not fully
  reproducible.
- The large Streamlit shell can encourage UI logic to bypass application
  services.
- AppKit/WebKit proves native shell independence but is not yet packaged,
  notarized, or validated across target macOS versions.
- Persisted technique detection currently relies on measurement shape because
  the JSONL record envelope predates an explicit technique discriminator.
- PySide6 6.11.1, 6.10.1, and 6.8.3 all failed to initialize their installed
  Cocoa plugin reliably across fresh target macOS 26 `zsh` login shells. Qt is
  removed; the shell now pins PyObjC 12.2.1 and uses AppKit directly.
- Cross-technique reasoning and provenance contracts are still early and may
  change as more instruments are integrated.

## Outstanding Issues

- Validate a legitimately sourced DLS export from another vendor/software
  version when available; synthetic locale, delimiter, single-angle, volume,
  and number variants are now covered.
- Validate OpenLab ingestion against more representative archives and add peak
  table, quantitation, system-suitability, calibration, audit-trail, and
  provenance coverage incrementally.

## Testing Status

- Latest result: `237 passed in 2.58s` from `scripts/test -q` on 2026-07-15.
- The Streamlit shell completed a headless startup and health smoke after task
  056.
- The native AppKit window launches from a fresh `zsh` login shell, opens its
  real NSOpenPanel, and renders the representative Lot 1 DLS result end to end.
- Three consecutive fresh login-shell launches succeeded after Qt removal.
- Task 010 added application list/restore coverage and desktop persisted-history
  document assertions; a clean-process AppKit controller import and an
  end-to-end list/restore smoke both passed.
- Supported development version: Python 3.12; verification used Python 3.12.13.
- Coverage includes models, DLS/multi-file ingestion, representative fixtures,
  metrics, aggregation, quality, history, filtration, chromatography/OpenLab,
  context memory, application contracts, investigator reasoning, and view
  models.
- Parser changes require synthetic and representative real-file validation.
- UI changes require a Streamlit smoke test in addition to unit tests.

## Next Recommended Task

- Objective: Run the final seven-read schema review and decide whether to
  replace `0.1-draft` with a stable contract version.
- Why this is next: Tasks 058 and 059 completed every functional item in the
  hardening gate. A deliberate freeze review is safer than changing the version
  as a side effect of implementation.
- Expected scope: Medium; capture golden success/error shapes, verify field
  semantics and pagination consistency, document compatibility promises, and
  either promote the contract or record specific blockers.
- Risks: Freezing accidental field names, conflating application DTO versions
  with transport versions, or promising remote security from a local policy.
- Success criteria: reviewed golden fixtures for all seven candidates and core
  errors, an explicit stable-version or remain-draft decision, and a clear
  go/no-go for selecting the first read-only transport.

## AI Context Window

When beginning a new implementation session, the minimum required reading is:

1. `docs/status/current-state.md`.
2. The relevant implementation prompt in `docs/prompts/`.
3. The relevant architecture or decision record linked by the prompt or this
   page.

Read additional documentation only when the task, affected contract, or links
from those three sources require it. This minimum does not override explicit
task instructions or repository agent rules.

## AI Agent Instructions

1. Read this document before substantial work.
2. Inspect `git status --short` and preserve unrelated or pre-existing changes.
3. Read the relevant architecture, decision, standard, and roadmap records.
4. Read or create the relevant numbered prompt in `docs/prompts/`.
5. Preserve backwards compatibility unless the task explicitly changes it.
6. Implement and test the smallest coherent requested change.
7. Update affected documentation and this page before declaring substantial
   work complete.
8. Run `graphify update .` after code or documentation changes.

## Documentation Map

- Current Status: [`current-state.md`](current-state.md)
- Architecture: [`../architecture/README.md`](../architecture/README.md),
  [`../architecture/capabilities.md`](../architecture/capabilities.md),
  [`../architecture/api-readiness.md`](../architecture/api-readiness.md),
  [`../ARCHITECTURE.md`](../ARCHITECTURE.md), and
  [`../STANDALONE_APP.md`](../STANDALONE_APP.md)
- Prompts: [`../prompts/README.md`](../prompts/README.md)
- Roadmap: [`../roadmap/README.md`](../roadmap/README.md) and
  [`../ROADMAP.md`](../ROADMAP.md)
- Standards: [`../standards/README.md`](../standards/README.md)
- Decision Records: [`../decisions/README.md`](../decisions/README.md)
- Vision: [`../VISION.md`](../VISION.md)
- Agent Handoff: [`../AGENT_HANDOFF.md`](../AGENT_HANDOFF.md)

## Update Rules

Update this document after:

- Architectural refactors or contract changes.
- New platform capabilities or completed implementation prompts.
- Major documentation changes or repository restructuring.
- Material changes to dependencies, runtime, test status, active work, known
  risks, outstanding issues, or the next recommended task.

Do not update this document after:

- Typo or formatting-only fixes.
- Isolated comments or cosmetic changes.
- Isolated unit-test changes that do not alter project behavior or direction.
- Trivial bug fixes with no architectural or handoff consequence.

Substantial work is complete only when this page reflects the resulting state,
its links are valid, `AGENTS.md` remains accurate, and architecture references
remain consistent.
