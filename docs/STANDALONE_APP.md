# Standalone Application Direction

LabAssistant is becoming a standalone application for laboratory experiment
intelligence. The current Streamlit surface is useful and should remain working,
but it is not the product boundary. It is the first human-facing shell around a
reusable application core.

## Product Boundary

LabAssistant should be framed as:

```text
Standalone app for scientists
  -> reusable experiment intelligence core
  -> stable read-only agent-access layer later
```

It should not be framed as:

```text
Streamlit upload tool
  -> charts
  -> optional AI wrapper
```

The core product is the experiment intelligence loop: define or upload an
experiment, gather evidence from available measurements, assess trustworthiness,
explain what happened, preserve context, and recommend practical next steps.

## Human Users First

Near-term app work should optimize for scientists using LabAssistant directly:

- Import DLS/Zetasizer, chromatography, filtration, and future instrument data.
- Review experiments rather than isolated files.
- See evidence quality, warnings, and recommended next checks quickly.
- Compare against prior experiments and local memory.
- Export experiment-level reports.
- Add human notes and provenance without losing traceability.

The app may continue to run through Streamlit while these workflows mature.
Future packaging could become a desktop app, local web app, or other dedicated
shell, but that choice should not leak into the scientific core.

## Desktop Prototype

The first desktop vertical slice uses PySide6 6.10.1 as a deliberately small native
macOS shell. `scripts/run-desktop` opens a Qt window, lets a scientist
select existing supported DLS files, and displays a concise analysis summary.
The desktop module calls `analyze_dls_dataset` from `labassistant.application`;
it does not import `app.py` or duplicate parsing, metrics, observation, or
experiment-assembly logic.

PySide6 adds a substantial dependency, but it works reliably with the project's
Homebrew Python 3.12 environment and provides a credible packaging path. The
framework remains isolated to the shell so another toolkit can replace it
without changing scientific or application contracts.

PySide6 is pinned because 6.11.1's Cocoa platform plugin did not initialize on
the target macOS 26 runtime even though the binary was installed. The launcher
also initializes Qt's plugin search paths explicitly for GUI-launch and remote
shell environments.

## Agent-Access Layer

Future agents should eventually be able to use LabAssistant, but the first
contract should be narrow and stable:

- Read app metadata and capability policy.
- List or fetch experiment summaries.
- Read normalized `Experiment`, `Observation`, report, and provenance data.
- Ask deterministic query/retrieval functions for compact context packets.
- Propose changes as explicit commands that a human can review.

Agent access should not begin with autonomous lab actions, instrument control,
remote hosting, or broad LLM prompt orchestration. Those remain non-goals until
the human app workflows, data model, provenance, and persistence boundaries are
stable.

The current foundation is `labassistant.application`, which includes:

- `app_manifest()`
- `agent_access_policy()`
- `build_experiment_snapshot(experiment)`
- `analyze_dls_dataset(paths)`

These are deliberately small. They provide a directionally stable app boundary
without committing to an HTTP server, plugin protocol, or agent runtime.

## Proposed Architecture Boundaries

Keep these boundaries visible as the app grows:

```text
UI shell
  Streamlit now; future desktop/local app possible.

Application services
  Commands and queries over experiments, history, memory, and reports.

Scientific core
  Models, ingestion, metrics, reasoning, observation generation, investigator.

Persistence and memory
  Local history, knowledge store, research journal, future storage migrations.

Agent access
  Read-only summaries first; reviewed commands later.
```

`app.py` should call application services and view-model builders. It should not
become the only place that knows how to assemble experiments, query memory, or
generate reports.

## Practical Phased Plan

### Phase A: Name The Boundary

- Keep the working Streamlit app stable.
- Document that Streamlit is the current shell, not the product identity.
- Expose a tiny app manifest and read-only experiment snapshot contract.
- Keep tests around the contract.

Status: started with `labassistant.application`.

The native desktop DLS vertical slice is delivered; packaging, notarization,
and visual refinement remain future work.

### Phase B: Move App Logic Behind Services

- Add application query functions for current experiment summaries, history
  lookup, memory retrieval, and report preview.
- Add application command functions for import, save, load, add note, and export.
- Keep commands deterministic and explicit.
- Keep Streamlit state as UI state only.

### Phase C: Stabilize Persistence Around Experiments

- Continue append-only history behavior.
- Treat `Experiment` as the stable persistence unit.
- Define migration expectations before replacing JSONL or SQLite pieces.
- Preserve provenance and source-file traceability.

### Phase D: Add Read-Only Agent Access

- Build local read-only APIs on top of application queries.
- Return snapshots and context packets before full raw payloads.
- Include schema/version fields in every public response.
- Require explicit human review for any write action.

### Phase E: Add Reviewed Agent Commands

- Introduce command objects only after the human app uses the same command path.
- Make commands auditable and reversible where possible.
- Never let agent clients bypass validation, provenance, or append-only history.

## Immediate Next Implementation Steps

1. Keep `labassistant.application` small and stable.
2. Add a `queries` module only when `app.py` has at least two repeated read
   workflows that can move out cleanly.
3. Add a `commands` module only when import/save/load/note/export workflows can
   share validation outside Streamlit.
4. Update docs and tests before changing persistence schemas.
5. Avoid adding an HTTP API, agent runtime, or LLM orchestration until the
   application service layer exists and is used by the human app.
