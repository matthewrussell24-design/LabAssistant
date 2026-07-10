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

- `app.py` calls importers, history functions, context retrieval, observation
  generation, investigation helpers, and brief builders directly.
- DLS and chromatography assembly cross the application boundary, but raw-file
  parsing and import preview orchestration remain UI-owned.
- Saved-history records are reconstructed into measurements inside `app.py`,
  duplicating logic already available in `labassistant.history`.
- Observation and brief generation are reusable functions, but they are not yet
  expressed as application capabilities.

Missing capability boundaries:

- Retrieve an experiment or experiment history.
- Compare experiments and find related prior work.
- Retrieve related scientific context.
- Generate normalized observations from supported evidence.
- Investigate an experiment and generate hypotheses.
- Produce an experiment-level report or brief.
- Add reviewed notes or other explicit memory commands independently of a full
  experiment save.

## Implemented Capability Catalog

| Stable name | Python entry point | Status |
| --- | --- | --- |
| `describe_platform` | `app_manifest` | Available |
| `describe_agent_access` | `agent_access_policy` | Available |
| `import_dls_experiment` | `dls_experiment_from_samples` | Available, transitional input |
| `import_chromatography_experiment` | `chromatography_experiment_from_preview` | Available, transitional input |
| `retrieve_experiment` | `retrieve_experiment` | Available; first used by Streamlit history loader |
| `retrieve_experiment_summary` | `build_experiment_snapshot` | Available |
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

## Candidate Capability Backlog

These are capability boundaries, not implemented public contracts:

| Candidate name | Scientific intent | Current owner |
| --- | --- | --- |
| `list_experiments` | Browse experiment history | History/UI |
| `compare_experiments` | Explain meaningful differences | History/UI |
| `find_related_experiments` | Find similar prior scientific work | History/UI |
| `retrieve_related_context` | Build a compact evidence-backed context packet | Context engine/UI |
| `generate_observations` | Normalize supported evidence into findings | Importers/observations/UI |
| `investigate_experiment` | Assess completeness and interpretability | Investigator/UI |
| `generate_hypotheses` | Produce deterministic, evidence-linked hypotheses | Technique modules/UI |
| `produce_investigation_summary` | Build an experiment-level brief/report | Observations/UI |
| `add_scientific_note` | Append a reviewed human note with provenance | Context engine/UI |

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

Define and test the canonical source for lot-level DLS `derived_metrics` so it
uses the richer per-angle evidence instead of intensity replicate 1 alone.
