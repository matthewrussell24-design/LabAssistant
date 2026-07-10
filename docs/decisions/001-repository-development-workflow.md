# Repository-Based Development Workflow

Status: Accepted
Date: 2026-07-10
Related Prompt: [`../prompts/001-adopt-development-workflow.md`](../prompts/001-adopt-development-workflow.md)

## Context

Project knowledge had been split between repository documents and chat history.
As LabAssistant grows, future contributors need a durable way to find requests,
standards, project direction, and the reasoning behind significant changes.

## Decision

The repository is the primary source of truth for substantial development work.
Each substantial request receives a numbered prompt in `docs/prompts/`; that
prompt is updated with implementation results. Relevant architecture, roadmap,
and standards documents are updated in the same change, and significant
technical decisions receive a record in `docs/decisions/`.

## Consequences

- Substantial changes include documentation work in their definition of done.
- Request history and implementation results remain together.
- New contributors can orient themselves without access to prior conversations.
- Routine fixes and cosmetic changes retain a lightweight workflow unless they
  alter an established contract or standard.
