# LabAssistant Documentation

This directory is the repository source of truth for project direction,
architecture, implementation history, engineering standards, and significant
technical decisions.

## Development Workflow

For substantial implementation work:

1. Read [`status/current-state.md`](status/current-state.md) and the relevant
   project documentation before making architectural changes.
2. Add or update the numbered request in `prompts/`.
3. Implement and test the requested change.
4. Update affected architecture, roadmap, or standards documentation.
5. Record significant architectural decisions in `decisions/`.
6. Update `status/current-state.md` when the work materially changes the project.
7. Complete the prompt's implementation summary, files changed, test results,
   and remaining work.

Routine bug fixes and cosmetic changes do not need architecture or decision
records unless they change an established contract or standard.

## Documentation Map

- [`status/current-state.md`](status/current-state.md) is the primary living
  handoff and the fastest way to understand the repository now.
- [`IDEAS.md`](IDEAS.md) is the inbox for promising ideas that are not yet
  approved or sequenced roadmap work.
- [`prompts/`](prompts/README.md) contains numbered implementation requests and
  their completion records.
- [`architecture/`](architecture/README.md) indexes current architecture
  documentation and owns future architecture-focused documents.
- [`roadmap/`](roadmap/README.md) indexes project direction and planned work.
- [`standards/`](standards/README.md) contains durable development and coding
  standards.
- [`decisions/`](decisions/README.md) contains records of significant technical
  and architectural decisions.

Current project documents that predate this directory structure remain at the
top of `docs/` and are indexed from the appropriate section above. Move or
replace them only as part of a separately scoped documentation change so
existing links remain valid.

For deeper historical handoff detail, read [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md).
For product direction, start with [`VISION.md`](VISION.md).
