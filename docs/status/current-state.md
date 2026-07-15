# LabAssistant Current State

**Project:** LabAssistant
**Version:** 0.1.0-dev
**Repository Root:** `LabAssistant/`
**Primary Branch:** `main`
**Architecture Version:** 2

## Repository State

- Current Branch: `main`
- Latest Completed Change: Built and qualified the first standalone arm64
  py2app artifact as an explicitly local-only non-release bundle (task 070).
- Working Tree: Task 070 is committed locally; inspect `git status --short`
  before beginning new work.
- Last Successful Test: `278 passed in 3.58s` from `scripts/test -q` on
  2026-07-15.
- Supported Python Version: Python 3.12; last verified with Python 3.12.13.
- Last Updated: 2026-07-15 for task 070.

## North Star

LabAssistant succeeds when a scientist can move from raw experimental data to a
well-supported scientific conclusion faster, with greater confidence, and with
full traceability.

## Project Health

- Architecture: 🟢 Healthy — target boundaries and migration direction are
  documented.
- Tests: 🟢 Healthy — 278 passing.
- Documentation: 🟢 Current — canonical status, navigation, prompts, and
  decisions are aligned.
- Application Layer: 🟢 Mature for current workflows — normalized DLS reads are
  Measurement-first, raw vendor inspection is explicitly adapter-bounded, and
  reusable human workflows cross typed application contracts.
- API Layer: 🟢 Local Transport Available — seven stable `1.0` reads are exposed
  through a bounded, same-user Unix-domain broker; no remote or write API exists.
- Agent SDK: 🟢 Read Client Available — typed local reads exist without an
  autonomous runtime or write access.

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
- ✅ API layer
- ✅ Agent SDK
- ⬜ Authentication
- ✅ Desktop prototype
- ✅ Polished desktop workspace
- ⬜ Packaged desktop application
- ⬜ Deployment

Checked items are present and tested, not necessarily final. Unchecked items
are future platform capabilities and are not automatically the next task.

## Current Milestone

- Milestone: macOS Packaging Readiness
- Status: Complete
- Goal: Define an honest reproducible path from development runtime to a
  distributable native macOS application.
- Current evidence: Task 057 audited all 42 registry entries, selected seven
  candidate reads, defined draft-to-stable versioning, and recorded a no-go for
  HTTP or agent transports until shared envelopes, stable errors, access
  boundaries, limits, and JSON conformance tests exist. Task 058 completed the
  envelopes, errors, safe invocation, and conformance tests without changing
  existing handlers. Task 059 added policy-derived local access and honest
  bounds/pagination metadata for every candidate collection. Task 060 captured
  golden shapes and retained `0.1-draft` because discovery exposes all 42
  registry entries and external/internal versions are conflated. Task 061
  resolved both blockers and promoted only the external seven-read contract to
  stable `1.0`; the internal registry remains unchanged. Task 062 selected a
  foreground Unix-domain read broker, documented same-user trust limits, and
  made peer-credential verification the implementation gate. Task 063 passed
  that gate on macOS/Python 3.12 and implemented bounded framing, broker-owned
  access mapping, safe socket lifecycle, and a diagnostic client.
  Task 064 added immutable capability-specific results and kept connection,
  transport, protocol, and stable application failures distinct.
  Task 065 selected a non-persistent `--share-local-reads` launch opt-in and
  defined ownership, collision, thread, shutdown, and packaging gates.
  Task 066 implemented that lifecycle, including cooperative broker stop,
  typed external collision probing, Cocoa termination cleanup, and a real native
  launch/read/shutdown smoke.
  Task 067 selected arm64 py2app, direct Developer ID distribution, hardened
  runtime, notarization, and no App Sandbox as the first target. Local ad-hoc
  bundles remain qualification-only; signing is blocked on an identity.
  Task 068 passed the first packaging gate with side-effect-free Application
  Support/Caches defaults and explicit safe copy-only legacy import.
  Task 069 passed the reproducibility gate with separate desktop, Streamlit,
  build, and development inputs plus deterministic hashed arm64 locks.
  Task 070 passed the local standalone gate with a 135-Mach-O arm64 py2app
  bundle, structural audit, packaged scientific smoke, and Launch Services
  open/quit. Its Homebrew Python payload requires macOS 26.0, so compatibility
  below the build host remains unqualified.

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
- `labassistant.local_read_transport` exposes only the stable seven-read
  projection through foreground owner-only Unix-domain IPC and derives access
  context from verified macOS peer credentials.
- `labassistant.local_read_client` exposes typed immutable methods for those
  seven reads; it does not start the broker or add autonomous behavior.
- `labassistant.desktop_read_sharing` owns optional process-bounded desktop
  sharing independently of AppKit state; normal desktop launch remains socket-free.
- `labassistant.runtime_paths` owns platform-native mutable locations and the
  explicit legacy-data import boundary without UI dependencies.
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
- The first local external transport is owner-only Unix-domain IPC, with access
  context derived by the broker rather than accepted from requests.
- Native desktop ownership of that broker must remain default-off and require
  explicit per-launch consent; compatible external brokers remain externally owned.
- The first macOS distribution is arm64, Developer ID signed, hardened,
  notarized, and non-sandboxed; local ad-hoc bundles are not releases.

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
- `labassistant/runtime_paths.py` — Application Support/Caches layout and safe
  explicit legacy-data import.
- `labassistant/measurements.py` and `dls_evidence.py` — DLS measurement and
  structural workspace-evidence adapters; `view_models.py` preserves legacy UI
  imports and `interpretation.py` owns presentation-ready summaries.
- `tests/` — unit, integration, importer, and representative-fixture coverage.
- `docs/` — status, prompts, architecture, roadmap, standards, decisions,
  vision, and technical proposals.
- `graphify-out/` — generated knowledge graph and architecture navigation data.
- `scripts/` — repository run and test entry points.
- `requirements/` — human-maintained dependency groups and generated Python
  3.12 macOS arm64 locks.
- `packaging/macos/` — non-release py2app entry and local qualification metadata.

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
- Captured golden success/error shapes and explicitly retained `0.1-draft` with
  two bounded release blockers (task 060).
- Added public-only discovery, independent external versioning, and promoted the
  golden seven-read contract to stable `1.0` (task 061).
- Selected Unix-domain IPC for the first local read transport and documented
  threat assumptions, framing, lifecycle, and implementation gates (task 062).
- Implemented the bounded foreground Unix-domain broker, diagnostic CLI, and
  same-user peer verification for all seven stable reads (task 063).
- Added the typed immutable local read client SDK with layered failures and
  seven capability-specific methods (task 064).
- Accepted a default-off, explicit-launch desktop broker lifecycle with bounded
  ownership, collision, shutdown, and packaging rules (task 065).
- Implemented the default-off desktop sharing flag, lifecycle owner, cooperative
  shutdown, and Cocoa termination cleanup (task 066).
- Audited macOS packaging and selected the first distribution target, runtime
  layout, signing/sandbox boundary, and verification gates (task 067).
- Centralized platform-native runtime paths and explicit copy-only legacy
  history/memory migration without CWD scanning (task 068).
- Split desktop, Streamlit, py2app-build, and development dependencies and
  generated reproducible hash-verified arm64 locks (task 069).
- Built and audited the first local-only standalone arm64 py2app artifact,
  including packaged scientific/runtime and Launch Services smoke (task 070).
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

- Local bundle task 070 is complete; `/tmp/LabAssistantQualification.app` is an
  ad-hoc host-qualification artifact, not a release.
- Deployment-runtime selection and a clean-machine compatibility matrix are the
  next gate.

## Known Risks

- Package boundaries remain partly DLS-shaped, increasing coupling during
  future extraction into application, ingestion, metrics, and reasoning areas.
- Parser validation does not yet cover enough vendor versions, locales,
  delimiters, workbook layouts, distribution types, or real OpenLab archives.
- JSONL history has limited migration and query support; schema evolution needs
  care until stronger persistence requirements justify a change.
- The large Streamlit shell can encourage UI logic to bypass application
  services.
- AppKit/WebKit is locally packaged but not Developer ID signed, notarized, or
  validated across target macOS versions. The qualification bundle works on the
  build host but its embedded Homebrew Python requires macOS 26.0.
- Persisted technique detection currently relies on measurement shape because
  the JSONL record envelope predates an explicit technique discriminator.
- PySide6 6.11.1, 6.10.1, and 6.8.3 all failed to initialize their installed
  Cocoa plugin reliably across fresh target macOS 26 `zsh` login shells. Qt is
  removed; the shell now pins PyObjC 12.2.1 and uses AppKit directly.
- Cross-technique reasoning and provenance contracts are still early and may
  change as more instruments are integrated.
- Unix-domain ownership proves a local OS user, not a distinct application; the
  selected first transport does not resist malicious same-user processes.

## Outstanding Issues

- Validate a legitimately sourced DLS export from another vendor/software
  version when available; synthetic locale, delimiter, single-angle, volume,
  and number variants are now covered.
- Validate OpenLab ingestion against more representative archives and add peak
  table, quantitation, system-suitability, calibration, audit-trail, and
  provenance coverage incrementally.

## Testing Status

- Latest result: `278 passed in 3.58s` from `scripts/test -q` on 2026-07-15.
- Task 070's first full run had one same-second Research Journal ordering
  failure; the isolated rerun and immediate full rerun passed. Treat recurrence
  as a persistence-ordering defect rather than a packaging failure.
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

- Objective: Select and qualify the Python runtime/deployment target for the
  first arm64 bundle, then define the clean-machine compatibility matrix.
- Why this is next: Task 070 proved the frozen application boundary but found
  macOS 11.0, 14.0, and 26.0 minimums; Homebrew Python 3.12.13 makes the current
  artifact effectively macOS 26-only and cannot support an honest product floor.
- Expected scope: Medium; compare controlled arm64 Python 3.12 runtime sources,
  inspect their Mach-O deployment targets and licensing/provenance, choose the
  highest justified minimum across runtime and wheels, parameterize the build,
  and run the existing audit/smoke on clean machines at the proposed minimum and
  current macOS.
- Risks: Rewriting deployment metadata without compatible binaries, relying on
  the build host, mixing runtime provenance, or claiming compatibility from a
  single machine.
- Success criteria: one documented reproducible Python runtime produces a clean
  arm64 bundle whose every Mach-O supports the declared minimum; packaged smoke
  passes on clean arm64 systems at that minimum and current macOS. No Developer
  ID signing, notarization, release upload, sandbox, or universal2 yet.

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
