# LabAssistant Capability Layer

The capability layer is the public language of LabAssistant. It describes what
a scientist can ask the platform to do independently of Streamlit, a future
desktop client, CLI, HTTP transport, or agent SDK.

Interfaces should call a capability when one exists instead of constructing or
mutating domain models directly. Domain models remain the scientific core;
capabilities own workflow entry, validation, orchestration, and stable outputs.

## Design Rules

- Name capabilities after scientific workflows, not implementation functions.
- Keep capability contracts independent of transport and interface framework.
- Prefer read-only, versioned outputs at external-facing boundaries.
- Preserve provenance and deterministic validation across every caller type.
- Keep parsers instrument-specific and reasoning instrument-independent.
- Add a capability only when it represents a coherent user intent.
- Preserve existing Python entry points while callers migrate incrementally.

The initial in-process registry lives in `labassistant.application`. It exposes
metadata and direct callable references. It is not an HTTP router, dependency
container, command bus, authentication layer, or permission system.

## Capability Audit

Existing application operations:

- Describe the platform and future agent-access policy.
- Assemble DLS evidence into an `Experiment`.
- Assemble chromatography evidence into an `Experiment`.
- Produce a read-only `ExperimentSnapshot`.
- Save an experiment and related hypotheses, recommendations, and notes to
  scientific memory.

Duplicated or bypassed workflows:

- `app.py` still coordinates some DLS import and decision-brief helpers directly.
- DLS assembly crosses the application boundary, but uploaded raw-file parsing
  and import-preview orchestration remain UI-owned.

The remaining visible bypass is the primary uploaded DLS import workflow.

## Implemented Capability Catalog

| Stable name | Python entry point | Status |
| --- | --- | --- |
| `describe_platform` | `app_manifest` | Available |
| `describe_agent_access` | `agent_access_policy` | Available |
| `import_dls_experiment` | `dls_experiment_from_samples` | Available, transitional input |
| `analyze_dls_dataset` | `analyze_dls_dataset` | Available; used by desktop prototype |
| `import_chromatography_experiment` | `chromatography_experiment_from_preview` | Available, transitional input |
| `analyze_chromatography_source` | `analyze_chromatography_source` | Available; used by Streamlit chromatography preview |
| `analyze_filtration_csv` | `analyze_filtration_csv` | Available; used by Streamlit filtration follow-up |
| `generate_observations` | `generate_observations` | Available; shared DLS, chromatography, and filtration normalization |
| `list_experiments` | `list_experiments` | Available; used by desktop History timeline |
| `compare_experiments` | `compare_experiments` | Available; used by Streamlit History panel |
| `find_related_experiments` | `find_related_experiments` | Available; used by Streamlit History panel |
| `retrieve_history_overview` | `retrieve_history_overview` | Available; used by Streamlit History panel |
| `retrieve_experiment` | `retrieve_experiment` | Available; first used by Streamlit history loader |
| `retrieve_experiment_summary` | `build_experiment_snapshot` | Available |
| `investigate_experiment` | `investigate_experiment` | Available; composed by experiment brief preview |
| `produce_experiment_brief` | `produce_experiment_brief` | Available; used by Streamlit Experiment Brief |
| `retrieve_related_context` | `retrieve_related_context` | Available; used by Streamlit memory panel |
| `retrieve_research_journal` | `retrieve_research_journal` | Available; used by Streamlit Research Journal |
| `add_scientific_note` | `add_scientific_note` | Available; explicit Streamlit journal write |
| `save_experiment_history` | `save_experiment_history` | Available; explicit Streamlit history write |
| `save_scientific_memory` | `save_experiment_to_memory` | Available |

`list_capabilities()` returns immutable `CapabilityContract` metadata.
`get_capability(name)` resolves one stable name or raises `KeyError`. Callers
invoke the referenced Python handler directly; the registry adds no transport.
`app_manifest()` publishes transport-neutral catalog metadata without exposing
Python handlers or domain objects.

## Describe Platform

**Name:** `describe_platform`

**Purpose:** Describe the LabAssistant product boundary, primary human surface,
and future access direction.

**Inputs:** None.

**Outputs:** A plain dictionary containing product identity, direction, primary
surface, and agent-access policy.

**Expected Errors:** None under normal operation.

**Caller Types:** Human UI, Agent, CLI, Future API.

## Describe Agent Access

**Name:** `describe_agent_access`

**Purpose:** Describe the reviewed boundaries and non-goals for future agent
clients without creating an agent runtime.

**Inputs:** None.

**Outputs:** An immutable `AgentAccessPolicy` with a dictionary representation.

**Expected Errors:** None under normal operation.

**Caller Types:** Human UI, Agent, CLI, Future API.

## Import DLS Experiment

**Name:** `import_dls_experiment`

**Purpose:** Assemble already parsed DLS sample evidence into an experiment and
generate its normalized observations.

**Inputs:** Parsed samples, optional experiment label, and optional source-file
names. `ParsedSample` is a transitional compatibility input until a neutral
import request contract is justified.

**Outputs:** An `Experiment` containing DLS measurements, observations,
provenance metadata, and a generated identifier.

**Expected Errors:** `TypeError` or `AttributeError` for malformed sample input.
Parser errors occur before this capability and are not yet normalized into
application-level errors.

**Caller Types:** Human UI, CLI, Future API. Agent use should wait for reviewed
file/provenance handling.

## Analyze Chromatography Source

**Name:** `analyze_chromatography_source`

**Purpose:** Import and analyze a chromatography CSV or OpenLab `.olax` source
without requiring a shell to select importers, build mass-balance reasoning, or
handle temporary archive files.

**Inputs:** A path or seekable uploaded source, optional label, and optional
source name. The `.csv` and `.olax` suffixes select the supported adapter.

**Outputs:** A versioned, frozen `ChromatographyAnalysisResult` containing an
experiment snapshot, immutable injection summaries, normalized observation
evidence, hypotheses, limitations, optional mass-balance assessment and trend
points, and archive summary counts. It contains no pandas DataFrames or mutable
measurements. `restore_experiment()` returns a fresh copy for an explicit memory save.

**Expected Errors:** `ValueError` for unsupported suffixes or invalid/empty CSV
evidence, `FileNotFoundError` for missing paths, and existing parser/archive
exceptions for malformed sources.

**Caller Types:** Human UI, CLI, Future API. Agent use is excluded pending
reviewed file and provenance handling. Streamlit is the first caller.

## Analyze Filtration CSV

**Name:** `analyze_filtration_csv`

**Purpose:** Parse filtration follow-up CSV evidence without exposing pandas or
the mutable importer result to interface shells.

**Inputs:** A path or file-like CSV source and optional source name.

**Outputs:** A versioned, frozen `FiltrationImportRead` containing immutable
measurement and trace summaries, normalized pressure/time units, warnings,
errors, missing columns, unsupported columns, and source provenance.
`restore_measurements()` returns fresh copies only for a reviewed attach action.

**Expected Errors:** Existing CSV read/parser exceptions. Missing required
columns and invalid rows remain structured diagnostics rather than exceptions.

**Caller Types:** Human UI, CLI, Future API. Agent use is excluded pending
reviewed file handling. Streamlit is the first caller; its explicit Attach
button remains responsible for matching and mutating current DLS evidence.

## Generate Observations

**Name:** `generate_observations`

**Purpose:** Normalize supported technique evidence into traceable scientific
findings through the established domain rules.

**Inputs:** A non-empty evidence list and explicit technique. DLS accepts parsed
samples; chromatography accepts measurements plus a mass-balance assessment;
filtration accepts filtration measurements.

**Outputs:** A frozen, versioned `ObservationGenerationResult` containing the
normalized technique and immutable `ObservationRead` values with label,
category, evidence, severity, confidence, source identity, and recommendation.
Internal experiment assembly can request fresh domain copies without exposing
mutable authoritative objects in serialized output.

**Expected Errors:** `ValueError` for empty evidence, unsupported techniques,
or a missing/inapplicable chromatography assessment; `TypeError` for evidence
that does not match the selected technique.

**Caller Types:** Human UI, Agent, CLI, Future API. DLS assembly,
chromatography restore, and chromatography CSV analysis are the first callers.

## Analyze Local DLS Dataset

**Name:** `analyze_dls_dataset`

**Purpose:** Run the supported multi-file DLS workflow from existing local
paths independently of any UI framework.

**Inputs:** One or more local CSV, text, XLS, or XLSX paths and an optional
experiment label.

**Outputs:** A versioned `DLSAnalysisResult` containing an
`ExperimentSnapshot`, concise immutable per-lot summaries, source paths, and
non-fatal import errors. Raw traces and mutable measurements remain inside the
scientific workflow.

**Expected Errors:** `ValueError` for an empty selection or a dataset with no
supported measurements; `FileNotFoundError` for a missing selected path;
existing parser exceptions for malformed files.

**Caller Types:** Human UI, CLI, Future API. The native AppKit desktop shell is
the first caller. Agent use is intentionally excluded.

## Import Chromatography Experiment

**Name:** `import_chromatography_experiment`

**Purpose:** Assemble an already parsed chromatography or OpenLab preview into
an experiment.

**Inputs:** Import preview, optional label, and optional source name. The preview
dictionary is transitional until importer result contracts stabilize.

**Outputs:** An `Experiment` containing chromatography measurements,
observations, hypotheses, assessment metadata, and source provenance.

**Expected Errors:** `TypeError`, `AttributeError`, or malformed-preview errors.
Archive and CSV parser errors occur before this boundary.

**Caller Types:** Human UI, CLI, Future API. Agent use should wait for reviewed
file/provenance handling.

## Retrieve Experiment Summary

**Name:** `retrieve_experiment_summary`

**Purpose:** Return compact, read-only experiment information without exposing
raw files, traces, measurements, or mutable observations.

**Inputs:** An existing `Experiment`.

**Outputs:** A versioned `ExperimentSnapshot` containing identity, technique,
instrument, evidence counts, and observation-category counts.

**Expected Errors:** `TypeError` or `AttributeError` when the supplied object is
not a valid experiment. A future persisted lookup capability should define
not-found errors separately.

**Caller Types:** Human UI, Agent, CLI, Future API.

## List Experiments

**Name:** `list_experiments`

**Purpose:** Enumerate persisted experiments for timeline browsing without
exposing mutable measurements or requiring an interface shell to read JSONL
storage directly.

**Inputs:** An optional history path for local or test storage.

**Outputs:** A tuple of frozen, metadata-only `ExperimentListing` records
(record id, saved time, label, measurement count, api version) ordered
newest-first. Same-second ties are broken by append order so the most recently
saved record sorts first, matching `latest_experiment`.

**Expected Errors:** None under normal operation. A missing history file yields
an empty tuple, and malformed JSONL lines are skipped so one damaged record
cannot hide the rest of the timeline.

**Caller Types:** Human UI, Agent, CLI, Future API. The native AppKit desktop
History timeline is the first caller.

## Retrieve Persisted Experiment

**Name:** `retrieve_experiment`

**Purpose:** Load one JSONL-backed experiment with its history provenance while
keeping persistence reconstruction outside interface shells.

**Inputs:** A record identifier and an optional history path for local or test
storage.

**Outputs:** A versioned, frozen `RetrievedExperiment` containing record
identity, saved time, label, and measurement count. `restore_measurements()`
returns fresh editable copies and `to_dict()` exposes metadata only.

**Expected Errors:** `ExperimentRecordNotFoundError` when the record or history
file does not exist; `MalformedExperimentRecordError` when targeted retrieval
cannot safely interpret the JSONL or measurement payload.

**Caller Types:** Human UI, Agent, CLI, Future API. The Streamlit saved DLS
experiment loader is the first caller.

## Retrieve History Overview

**Name:** `retrieve_history_overview`

**Purpose:** Return persisted experiment-level summaries and sample-level DLS
trend evidence without requiring interface shells to read JSONL or derive
history metrics.

**Inputs:** An optional history path for local or test storage.

**Outputs:** A versioned, frozen `HistoryOverview` containing immutable
`HistorySummary` and `HistoryTrendPoint` tuples. Summary order preserves JSONL
append order; trend points preserve experiment and measurement order.

**Expected Errors:** None under normal operation. Missing history yields empty
tuples and malformed lines retain the tolerant history-reader behavior.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit is the first caller.

**Restore composition:** `restore_dls_experiment(record_id)` is a supporting
application function (not a separate catalog entry) that composes
`retrieve_experiment` with the shared DLS summary assembly and returns a
`DLSAnalysisResult`. It lets the desktop reopen a saved record through the same
read model as a fresh import without reading storage or recomputing metrics.

`restore_chromatography_experiment(record_id)` is the corresponding
technique-aware composition for HPLC evidence. It reconstructs nested peaks and
chromatogram traces, annotates history provenance, reruns deterministic
mass-balance assessment and observation generation, and returns a frozen
`ChromatographyRestoreResult` with immutable injection summaries. DLS, empty,
and malformed chromatography records are rejected with
`MalformedExperimentRecordError`; the JSONL schema is unchanged.

## Compare Experiments

**Name:** `compare_experiments`

**Purpose:** Explain sample-level Z-average and PDI changes between current DLS
evidence and a selected or latest persisted experiment.

**Inputs:** Current `Measurement` objects, an optional baseline record ID, an
optional record ID to exclude from latest selection, and an injectable history
path.

**Outputs:** A versioned, frozen `ExperimentComparison` containing immutable
sample rows, baseline metadata, drift labels, and a drifted-sample count. Empty
history produces no baseline and labels current rows as new samples.

**Expected Errors:** Explicit lookup preserves existing not-found and malformed
record errors. Automatic latest selection tolerates absent history.

**Caller Types:** Human UI, Agent, CLI, Future API. Threshold crossings do not
claim scientific causality.

## Find Related Experiments

**Name:** `find_related_experiments`

**Purpose:** Rank saved DLS samples by proximity to one query measurement using
the established size and PDI feature distance.

**Inputs:** A query `Measurement`, optional top-N limit, optional record ID to
exclude, and an injectable history path.

**Outputs:** A versioned, frozen `RelatedExperiments` envelope containing
immutable ranked matches. Similarity is a readability score derived from
distance, not a probability.

**Expected Errors:** `ValueError` when `top_n` is less than one. Missing or empty
history returns an empty match tuple.

**Caller Types:** Human UI, Agent, CLI, Future API. Relatedness indicates feature
proximity and must not be presented as causal evidence.

## Save Experiment History

**Name:** `save_experiment_history`

**Purpose:** Append explicitly confirmed experiment evidence to local JSONL
history without exposing the persistence writer to interface shells.

**Inputs:** One or more serializable measurements, an optional label, optional
loaded-record identity and label for append-only lineage, and an injectable
history path.

**Outputs:** A frozen, versioned `ExperimentSaveReceipt` containing record
identity, saved timestamp, normalized label, measurement count, and optional
source record identity. Evidence is copied before lineage is added, so the
active analysis is not mutated by saving.

**Expected Errors:** `ValueError` for empty evidence, `TypeError` for evidence
without the established `to_dict()` serialization contract, and local I/O
errors when persistence fails.

**Caller Types:** Human UI and CLI only. Agent and Future API use are excluded
because this is an explicit reviewed write. Streamlit is the first caller.

## Save Scientific Memory

**Name:** `save_scientific_memory`

**Purpose:** Persist an experiment and its related hypotheses,
recommendations, tags, and optional human note as scientific memory.

**Inputs:** `Experiment`, optional human note, project identifier, tags, and an
optional injected `KnowledgeStore`.

**Outputs:** None. Success means all requested records were accepted by the
store.

**Expected Errors:** Invalid experiment errors and local persistence/database
errors. Atomicity and application-level error normalization remain undefined;
callers must not imply a successful save after an exception.

**Caller Types:** Human UI and CLI. Future API or Agent callers require reviewed
write commands, authorization, audit behavior, and explicit human approval.

## Retrieve Related Scientific Context

**Name:** `retrieve_related_context`

**Purpose:** Retrieve a compact, deterministic context packet from local
scientific memory without exposing the mutable store or arbitrary payloads.

**Inputs:** A non-empty keyword question, optional required tags, positive
result limit, and injectable knowledge-store path or store.

**Outputs:** A versioned, frozen `RelatedScientificContext` containing immutable
items grouped as experiments, observations, supporting evidence, hypotheses,
recommendations, notes, and source files. Items retain identity, experiment,
project, instrument, source, tag, confidence, and timestamp provenance.

**Expected Errors:** `ValueError` for an empty question or limit below one.
Missing or empty memory returns a low-confidence packet with the established
empty-memory caveat.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's local-memory
context panel is the first caller.

## Retrieve Research Journal

**Name:** `retrieve_research_journal`

**Purpose:** List and export the deterministic Research Journal without
exposing its mutable store or grouping implementation.

**Inputs:** Optional keyword, tag, instrument, and sample filters plus an
injectable knowledge-store path or store.

**Outputs:** A versioned, frozen `ResearchJournalRead` containing immutable
grouped entries in newest-first order and the exact matching Markdown export.
Entries retain identity, experiment, instrument, tags, samples, observations,
hypotheses, recommendations, source files, notes, and timestamps.

**Expected Errors:** Local SQLite read errors. Empty or unmatched memory returns
an empty entry tuple and the established no-matches Markdown document.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's Research Journal
panel is the first caller. Standalone note creation is not part of this read query.

## Add Scientific Note

**Name:** `add_scientific_note`

**Purpose:** Persist one explicitly confirmed standalone human note to local
scientific memory and return immutable receipt metadata.

**Inputs:** Required non-empty text; optional title, instrument identifier,
tags, and injectable knowledge-store path or store. Whitespace is trimmed,
blank titles become `Research note`, blank instruments are omitted, and tags
retain the store's normalized/deduplicated ordering.

**Outputs:** A frozen `ScientificNoteReceipt` containing item ID, title,
instrument, tags, human confidence, timestamp, and API version. Note text is
not echoed in the receipt.

**Expected Errors:** `ValueError` for empty note text and local SQLite write errors.

**Caller Types:** Human UI and CLI only. The explicit Streamlit button action is
the first caller. Agent and Future API callers are intentionally excluded until
authorization, approval, and audit policies exist.

## Investigate Experiment

**Name:** `investigate_experiment`

**Purpose:** Assess experiment completeness and interpretability from its
normalized observation stream without exposing the mutable domain report.

**Inputs:** An `Experiment` containing normalized observations.

**Outputs:** A versioned, frozen `ExperimentInvestigation` containing the five
canonical question/answer findings, completeness and interpretability state,
confidence improvements, highlights, severity counts, and immutable observation
evidence with source provenance.

**Expected Errors:** `TypeError` or `AttributeError` for invalid experiment or
observation inputs. Empty observations return a valid non-interpretable result.

**Caller Types:** Human UI, Agent, CLI, Future API. The experiment brief preview
is the first composed application caller.

## Produce Experiment Brief

**Name:** `produce_experiment_brief`

**Purpose:** Compose an instrument-independent report preview from an Experiment
without coupling scientific reasoning to Streamlit, document export, or DLS-only
decision ranking.

**Inputs:** One `Experiment` containing its normalized observations and evidence counts.

**Outputs:** A deeply frozen, versioned `ExperimentBriefPreview` containing an
immutable experiment identity, summary, completeness and interpretability state,
five canonical report sections, and immutable observation evidence. Serialization
returns plain dictionaries and lists without exposing domain models or DataFrames.

**Expected Errors:** `TypeError` when the input is not an `Experiment`. Empty
observation streams produce a valid non-interpretable preview through the established
Investigator behavior.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's generic Experiment
Brief is the first direct caller.

## Candidate Capability Backlog

These are capability boundaries, not implemented public contracts:

| Candidate name | Scientific intent | Current owner |
| --- | --- | --- |
| `generate_hypotheses` | Produce deterministic, evidence-linked hypotheses | Technique modules/UI |

Promote candidates one at a time when an existing human workflow can become the
first real caller. Define typed inputs, stable read outputs, validation, and
focused compatibility tests during promotion.

## Error Direction

The initial capabilities preserve current exceptions for backwards
compatibility. Do not add an exception hierarchy solely for architectural
symmetry. Introduce small application-level errors only when at least two
capabilities need consistent handling for invalid input, not found, conflict,
unsupported evidence, or persistence failure.

Network status codes and authentication failures do not belong in this layer.

## Domain Boundary

Current import capabilities return `Experiment` because the human UI and
scientific core already use that model. This is a transitional in-process
contract, not permission for remote clients to mutate domain objects.

External-facing readers should prefer versioned snapshots or future report and
context contracts. New callers should not construct `Experiment`,
`Observation`, or persistence records when a capability can perform the same
workflow with validation and provenance.

## Recommended Next Step

Promote additional UI-owned workflows only when a second shell or existing
human workflow needs them. Keep desktop packaging and richer presentation
separate from scientific capability contracts.
