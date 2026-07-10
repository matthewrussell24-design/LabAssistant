# Living Project Status as the Primary Handoff

Status: Accepted
Date: 2026-07-10
Related Prompt: [`../prompts/002-establish-living-project-status.md`](../prompts/002-establish-living-project-status.md)

## Context

Implementation context was distributed across chat history, roadmap material,
architecture notes, and a long historical agent handoff. Contributors need a
single, current entry point that can be read quickly and updated continuously.

## Decision

`docs/status/current-state.md` is the primary handoff between implementation
sessions. Every substantial task must review and update it before completion
when the work materially changes architecture, modules, dependencies, runtime,
tests, platform direction, roadmap completion, outstanding issues, or the next
recommended task.

There will be only one `current-state.md`. It is a living snapshot, not an
append-only history or architecture decision log.

## Consequences

- Substantial work is incomplete until the status page accurately reflects the
  resulting repository state.
- New contributors have one fast, canonical orientation path.
- Detailed rationale and history remain in prompts, architecture documents, and
  decision records rather than accumulating indefinitely in the status page.
- Typo, formatting, isolated-comment, and trivial bug-fix changes with no
  architectural consequence do not require status churn.
