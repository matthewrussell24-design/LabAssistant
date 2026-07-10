# Adopt the LabAssistant Development Workflow

Status: Completed
Created: 2026-07-10
Last Updated: 2026-07-10
Priority: High
Depends On: None

## Objective

Establish a permanent repository-based development workflow so future LabAssistant
implementation work is consistent, documented, and understandable without prior
chat history.

## Context

LabAssistant is evolving beyond a single Streamlit application into a standalone
scientific platform. Architecture decisions, implementation requests, standards,
and project direction therefore need durable homes in the repository.

## Tasks

- Create focused directories for prompts, architecture, roadmap, standards, and
  decisions.
- Explain the purpose and use of each directory.
- Provide a reusable implementation prompt template.
- Record this request as prompt `001` and update it on completion.
- Make the documentation index discoverable from the repository README.
- Record the decision to treat documentation as part of substantial
  implementation work.

## Deliverables

- A navigable documentation index in `docs/README.md`.
- Numbered prompt guidance and a reusable template.
- Architecture, roadmap, standards, and decision indexes.
- A repository-level link to the documentation index.
- A completed historical record of this implementation.

## Success Criteria

A new human or AI coding agent can find the project organization, prompt
history, architecture documents, roadmap, engineering standards, and decision
records without relying on chat history.

## Implementation Summary

Established the requested directory-based documentation workflow while keeping
the repository's existing top-level project documents in place. Added a central
documentation index, prompt lifecycle and template, indexes for architecture and
roadmap material, a durable development standard, and the first decision record.
Linked the workflow from the root README.

## Files Changed

- Modified `README.md`.
- Created `docs/README.md`.
- Created `docs/prompts/README.md`, `docs/prompts/TEMPLATE.md`, and this prompt.
- Created `docs/architecture/README.md`.
- Created `docs/roadmap/README.md`.
- Created `docs/standards/README.md`.
- Created `docs/decisions/README.md` and
  `docs/decisions/001-repository-development-workflow.md`.

## Test Results

- Verified every requested directory and README exists.
- Verified the root README links to `docs/README.md`.
- Verified the prompt template contains all required request and completion
  sections.
- Ran `graphify update .` after the documentation changes.

## Remaining Work

No work remains for this request. Future substantial changes should create the
next numbered prompt and follow the documented workflow.
