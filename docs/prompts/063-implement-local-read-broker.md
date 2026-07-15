# Implement Local Read Broker

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 062 - Select Local Read Transport

## Objective

Implement the minimal foreground Unix-domain broker selected by ADR 004 and
prove an independent local client can use exactly the stable seven-read surface.

## Tasks

- Prove supported macOS/Python peer-credential retrieval and fail closed.
- Add bounded transport framing and broker-owned access mapping.
- Add guarded socket startup, stale cleanup, and foreground shutdown.
- Add a diagnostic CLI client and focused integration coverage.

## Success Criteria

The broker verifies same-user peers, exposes exactly seven stable reads, rejects
unsafe paths and invalid frames without leaking internals, cleans up its socket,
and passes full verification without adding writes or a network listener.

## Implementation Summary

- Proved macOS `getpeereid` against a real Python 3.12 socket pair and isolated
  the platform resolver behind a fail-closed interface.
- Added bounded request/response framing, strict public capability and field
  allowlists, stable-envelope preservation, and broker-owned access context.
- Added owner-only runtime/socket modes, explicit path-length handling, active
  broker refusal, safe stale-socket cleanup, and normal shutdown cleanup.
- Added foreground and diagnostic launch scripts plus independent-process
  public/protected read smoke coverage.

## Files Changed

- `labassistant/local_read_transport.py`
- `labassistant/api_readiness.py`
- `scripts/run-read-broker`
- `scripts/read-api`
- `tests/test_local_read_transport.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/architecture/api-readiness.md`
- `docs/status/current-state.md`
- `docs/prompts/063-implement-local-read-broker.md`

## Test Results

- Focused transport/API tests: 15 passed in 0.56s.
- Full suite: 248 passed in 2.53s.
- Markdown links validated across 91 documentation files.
- Independent-process smoke: public discovery and protected experiment listing
  succeeded through the launch scripts; `Ctrl-C` removed the socket.

## Remaining Work

- Define the first typed local client SDK over this transport before adding any
  agent runtime or desktop-managed broker lifecycle.
