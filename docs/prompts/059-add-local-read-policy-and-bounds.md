# Add Local Read Policy And Bounds

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 058 - Add API Conformance Envelopes

## Objective

Replace the trusted access boolean with an explicit local policy decision and
bound every candidate collection response with honest pagination metadata.

## Tasks

- Define immutable access context and decision contracts.
- Require known local clients, a non-empty subject, local origin, and the
  capability's required read scope.
- Add limit/offset output paging for experiment lists, history, and journal.
- Preserve related-context category limits and report their bounded status
  without inventing totals or cursors.
- Keep existing application handlers and filesystem/store ownership unchanged.

## Success Criteria

Protected candidate reads require a policy-derived decision, collection outputs
are deterministically bounded with explicit metadata, and the final draft freeze
review is the only remaining readiness task.

## Implementation Summary

- Added immutable local access context, decision, and policy contracts.
- Required a named subject, known local client, explicit local origin, and
  capability-specific `history:read` or `memory:read` scope.
- Replaced the trusted boolean with policy evaluation while keeping access
  context outside request parameters.
- Added limit/offset pagination to experiment lists, history collections, and
  journal entries, including page-scoped Markdown.
- Added honest per-category bounds to related context; unknown totals remain
  `null` instead of implying a cursor the store cannot support.

## Files Changed

- `labassistant/api_readiness.py`
- `tests/test_api_readiness.py`
- `docs/architecture/api-readiness.md`
- `docs/architecture/capabilities.md`
- `docs/status/current-state.md`
- `docs/prompts/059-add-local-read-policy-and-bounds.md`

## Test Results

- Focused access/pagination/API conformance coverage: 4 passed.
- Full suite: 237 passed in 2.58s.

## Remaining Work

- Run the final schema-shape review and decide whether the seven-read contract
  can move from `0.1-draft` to a stable version before transport selection.
