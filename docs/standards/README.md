# Development Standards

This directory contains durable engineering and documentation standards for
LabAssistant.

## Substantial Work

Substantial work includes new capabilities, platform refactors, architecture or
API boundary changes, dependency or runtime changes, and new engineering
standards. For this work:

1. Read the relevant documentation before changing architecture.
2. Create or update a numbered file in `docs/prompts/`.
3. Implement the scoped change and tests.
4. Update affected documentation as part of the implementation.
5. Summarize the implementation in the original prompt.
6. Record significant architectural decisions in `docs/decisions/`.
7. Review and update `docs/status/current-state.md` before declaring the task
   complete.

Prompt filenames use a three-digit sequence and a short kebab-case description,
for example `002-add-experiment-model.md`. Start from
[`../prompts/TEMPLATE.md`](../prompts/TEMPLATE.md).

Routine bug fixes and cosmetic changes do not require architecture or decision
records unless they change an established contract, behavior, or standard.
They also do not require a status update when they are limited to typos,
formatting, isolated comments, or trivial fixes with no architectural effect.

Repository-specific agent instructions remain in [`../../AGENTS.md`](../../AGENTS.md).
