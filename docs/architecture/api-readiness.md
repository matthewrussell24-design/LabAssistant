# API Readiness

This page answers one question: which application capabilities are safe to
freeze for an external read-only transport, and what must happen first?

## Decision

Transport implementation is **not ready yet**. The application layer is mature,
but every registry entry still carries the draft version `0.1-draft`, there is
no common response/error envelope, and no external read-access boundary exists.

The first transport should expose only seven read candidates after the bounded
hardening gate below. Registry presence does not imply external stability.

## Classifications

- **Candidate read** — scalar/filter inputs and a read-only serializable result;
  eligible for the first freeze after the common gate.
- **In-process read** — useful read whose inputs are domain objects, workspace
  evidence, paths, file-like sources, or other Python-only collaborators.
- **Sensitive read** — returns full raw source or local scientific-memory
  content and needs an explicit access/content policy.
- **Reviewed write** — changes local evidence or persistence and remains human/
  CLI-only until authorization, confirmation, idempotency, and audit rules exist.
- **Assembly** — returns or consumes mutable domain objects; not a transport DTO.

## Complete Capability Inventory

| Capability | Classification | External blocker |
| --- | --- | --- |
| `describe_platform` | Candidate read | Common envelope and stable version |
| `describe_agent_access` | Candidate read | Common envelope and stable version |
| `import_dls_experiment` | Assembly | Workspace input and mutable `Experiment` output |
| `analyze_dls_dataset` | In-process read | Server-local paths and file-access policy |
| `analyze_dls_uploads` | In-process read | Upload request contract and size/type limits |
| `rank_dls_decisions` | In-process read | DLS workspace/session input |
| `compose_dls_narrative` | In-process read | DLS workspace/session input |
| `summarize_dls_health` | In-process read | DLS workspace/session input |
| `analyze_dls_trend_diagnostics` | In-process read | DLS workspace/session input |
| `retrieve_dls_circulation_time` | In-process read | Sample identity/session contract and nullable envelope |
| `set_dls_circulation_time` | Reviewed write | Authorization, confirmation, idempotency, audit |
| `analyze_dls_forward_scatter_trends` | In-process read | DLS workspace/session input |
| `retrieve_dls_filtration_measurement` | In-process read | Sample identity/session contract and nullable envelope |
| `set_dls_filtration_measurement` | Reviewed write | Authorization, confirmation, idempotency, audit |
| `attach_dls_filtration_measurements` | Reviewed write | Batch command DTO, partial-failure and audit policy |
| `analyze_filtration_follow_up_trends` | In-process read | DLS workspace/session input |
| `generate_filtration_relationship_hypothesis` | In-process read | Composed Python DTO inputs |
| `assess_dls_aggregation` | In-process read | DLS workspace/session input |
| `summarize_dls_samples` | In-process read | DLS workspace/session input |
| `retrieve_dls_angle_details` | In-process read | DLS workspace/session input |
| `retrieve_dls_metrics` | In-process read | DLS workspace/session input |
| `retrieve_dls_distributions` | In-process read | DLS workspace/session input |
| `retrieve_dls_raw_evidence` | Sensitive read | Full-source policy, size limits, adapter/session input |
| `retrieve_dls_correlograms` | In-process read | DLS workspace/session input |
| `retrieve_dls_paired_angle_overlays` | In-process read | DLS workspace/session input |
| `import_chromatography_experiment` | Assembly | Preview dictionary and mutable `Experiment` output |
| `analyze_chromatography_source` | In-process read | Upload request contract and size/type limits |
| `analyze_filtration_csv` | In-process read | Upload request contract and size/type limits |
| `generate_observations` | Assembly | Technique-specific domain inputs and copy-on-access output |
| `list_experiments` | Candidate read | Versioned list envelope and read authorization |
| `compare_experiments` | In-process read | Current Measurement/workspace input |
| `find_related_experiments` | In-process read | Query Measurement input |
| `retrieve_history_overview` | Candidate read | Common envelope and read authorization |
| `retrieve_experiment` | Candidate read | Common errors, read authorization, not-found mapping |
| `retrieve_experiment_summary` | In-process read | Mutable `Experiment` input |
| `investigate_experiment` | In-process read | Mutable `Experiment` input |
| `produce_experiment_brief` | In-process read | Experiment/workspace union input |
| `retrieve_related_context` | Candidate read | Common envelope, read authorization, bounded pagination |
| `retrieve_research_journal` | Candidate read | Common envelope, read authorization, bounded pagination |
| `add_scientific_note` | Reviewed write | Authorization, confirmation, idempotency, audit |
| `save_experiment_history` | Reviewed write | Serializable command DTO, idempotency, conflict policy |
| `save_scientific_memory` | Reviewed write | Serializable command DTO, authorization, audit |

## First Freeze Candidate

The candidate read surface is:

1. `describe_platform`
2. `describe_agent_access`
3. `list_experiments`
4. `retrieve_history_overview`
5. `retrieve_experiment`
6. `retrieve_related_context`
7. `retrieve_research_journal`

This is a candidate, not an authorization grant. Scientific history, context,
and journal reads require a local access policy even when the first transport is
loopback-only.

## Hardening Gate

Before selecting or implementing a transport:

1. Add one transport-neutral success envelope containing `api_version`,
   `capability`, and `data`.
2. Add one typed error envelope and stable codes for invalid input, not found,
   conflict, unsupported evidence, access denied, and internal failure.
3. Wrap `list_experiments` in a versioned result instead of a bare tuple.
4. Define bounded pagination/limits for history, context, and journal reads.
5. Define the local read-access boundary and ensure store/path collaborators
   cannot be supplied by an external request.
6. Add JSON round-trip/schema-shape tests for all seven candidates.
7. Replace `0.1-draft` only when those tests and rules are complete.

## Go/No-Go

**No-go for an HTTP server or agent SDK today.**

**Go for the next task:** implement the shared transport-neutral response/error
envelopes and candidate-read conformance tests inside the application package.
That work does not choose a framework, open a port, or grant write access.

## Deliberate Deferrals

- File upload and server-local path APIs.
- DLS workspace/session handles.
- Raw source retrieval.
- Reviewed writes.
- Authentication mechanism selection.
- HTTP framework, process model, deployment, and agent runtime.
