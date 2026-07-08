# Context Engine

LabAssistant's Context Engine is the memory foundation for a scientific second
brain. It is not a chatbot and it does not dump the full experiment database into
an AI prompt. Its job is to persist structured scientific memory and retrieve a
small, relevant context packet for a specific question.

## Memory Layers

The first implementation uses five explicit layers:

| Layer | Purpose | Examples |
| --- | --- | --- |
| Experiment memory | What happened in specific analytical runs | experiments, measurements, observations, source files |
| Project memory | Cross-experiment context within a program | stability project, formulation campaign, lot history |
| Instrument memory | Instrument- and method-specific context | Agilent 1290 HPLC, DLS instrument, method caveats |
| Scientific memory | Interpretive scientific knowledge | hypotheses, recommendations, mass-balance reasoning |
| Human notes | User-authored lab context | operator notes, sample-prep notes, decisions |

The boundary is intentional: importers produce experiment memory, scientists add
human notes, and deterministic/LLM reasoning can later write scientific memory.

## Knowledge Store

The local `KnowledgeStore` lives in [context_engine.py](/Users/matthew/Documents/LabAssistant/labassistant/context_engine.py:1).
It starts with SQLite at `.labassistant_memory/knowledge.sqlite`.

It persists one `knowledge_items` table with:

- `layer`
- `entity_type`
- `title`
- `text`
- `experiment_id`
- `project_id`
- `instrument_id`
- `source_id`
- `tags`
- `confidence`
- `payload_json`
- `created_at`

Supported entity types:

- `experiment`
- `measurement`
- `observation`
- `evidence`
- `hypothesis`
- `recommendation`
- `note`
- `source_file`

Raw structured objects are preserved in `payload_json`; compact searchable text
is kept separately so retrieval does not need to deserialize every scientific
object into a future prompt.

## Context Retriever

`ContextRetriever.retrieve(question)` performs deterministic keyword/tag search
and assembles a `ContextPacket`:

- relevant experiments
- relevant observations
- supporting evidence
- hypotheses
- recommendations
- related notes
- source files
- missing information
- confidence
- caveats

The packet is deliberately compact. It is suitable for a future Investigator,
report generator, or LLM prompt builder, but it is not itself an answer.

## Research Journal

The Research Journal is a deterministic view over the same `KnowledgeStore`.
Saved experiments become journal entries grouped by `experiment_id`; standalone
manual notes become note-only entries. Each entry can show:

- date/time
- experiment name
- instrument
- samples
- tags
- key observations
- hypotheses
- recommendations
- source files
- human notes

The app exposes this as a `Research Journal` expander. Users can add manual
notes, filter by keyword/tag/instrument/sample, and export the current journal
view to Markdown. No LLM generation is used; Markdown export is a direct render
of stored memory.

## Current Retrieval Rules

The initial retriever uses:

- tokenized keyword matching over title, text, tags, IDs, layer, and entity type
- optional tag filtering
- simple ranking that slightly favors experiments and observations
- deterministic missing-information detection from `data_completeness`,
  `missing`, `unsupported`, and `missing_information`
- confidence based on whether relevant evidence exists and whether gaps are
  present

There are no embeddings, no cloud database, and no LLM dependency.

## Import Path

`KnowledgeStore.add_experiment(experiment)` ingests the current LabAssistant
`Experiment` model:

- `Experiment` becomes experiment memory
- each measurement becomes a measurement item
- each observation becomes an observation item
- observation recommendations become recommendation items
- unsupported sections become evidence/missing-information items
- source files become source-file items

This preserves DLS and chromatography workflows because importers do not need to
change. They can continue producing `Measurement`, `ChromatographyMeasurement`,
`Observation`, and `Experiment` objects; memory ingestion is a separate step.

## Non-Goals For This Phase

- No chatbot.
- No cloud database.
- No embeddings/vector search.
- No automatic LLM summarization.
- No replacement of DLS history JSONL.
- No prompt stuffing.

## Next Steps

- Add app-level controls for saving an imported `Experiment` into the knowledge
  store.
- Add project and instrument profile editors.
- Add provenance views showing which source files support each packet.
- Add richer retrieval filters by technique, sample, date, method, and severity.
- Add richer journal grouping by project/week once project memory matures.
- Later: add embeddings as an optional index while keeping the structured store
  authoritative.
