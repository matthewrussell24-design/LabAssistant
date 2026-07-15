# Audit API Readiness

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 056 - Isolate DLS Raw Evidence Adapter

## Objective

Classify the mature application capability surface before selecting an HTTP or
agent transport.

## Tasks

- Inventory every registered capability, input shape, output serialization,
  error behavior, and write authorization.
- Separate candidate public reads from in-process workflows and reviewed writes.
- Define draft-to-stable versioning and breaking-change rules.
- Identify a bounded hardening backlog and transport go/no-go decision.

## Success Criteria

The repository has one concise API-readiness map covering all registered
capabilities, explicit version rules, a candidate first public surface, and a
clear next implementation task without adding a server.

## Implementation Summary

- Audited all 42 registered capabilities against their Python signatures,
  frozen/read DTOs, `to_dict()` paths, caller policy, persistence behavior, and
  sensitive raw content.
- Identified seven candidate read operations, while keeping object-based DLS
  workflows, ingestion, raw evidence, and all writes draft/in-process.
- Established schema version and error-envelope rules in ADR 003.
- Recorded a no-go for transport implementation until the shared envelope and
  read-access boundary exist.

## Files Changed

- `docs/architecture/api-readiness.md`
- `docs/architecture/capabilities.md`
- `docs/decisions/003-api-contract-freeze-policy.md`
- `docs/decisions/README.md`
- `docs/status/current-state.md`
- `docs/prompts/057-audit-api-readiness.md`

## Test Results

- Documentation link and consistency checks passed.
- Full application suite: 233 passed in 2.74s.

## Remaining Work

- Implement and test a transport-neutral response/error envelope for the seven
  candidate reads before choosing a server framework or agent SDK.
