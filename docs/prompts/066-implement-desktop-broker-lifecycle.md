# Implement Desktop Broker Lifecycle

Status: Complete
Created: 2026-07-15
Last Updated: 2026-07-15
Priority: High
Depends On: 065 - Decide Desktop Broker Lifecycle

## Objective

Implement ADR 005's explicit desktop read-sharing opt-in with cooperative,
process-bounded broker ownership and unchanged default startup.

## Tasks

- Add cooperative broker stop/unblock behavior.
- Add an AppKit-independent lifecycle owner and compatible collision probe.
- Parse `--share-local-reads` separately from positional dataset paths.
- Wrap the native run loop in safe status and idempotent cleanup.
- Test default-off, owned, external, unavailable, and shutdown behavior.

## Success Criteria

Default desktop startup creates no socket; opted-in startup serves typed reads
and cleans up only its owned socket on every exit path, without adding hidden
startup, persistence, writes, or remote access.

## Implementation Summary

- Added cooperative accept-loop polling and close/unblock behavior to the broker.
- Added an AppKit-independent desktop owner with owned, external, unsafe,
  incompatible, unavailable, disabled, and shutdown-failed states.
- Added typed compatible-broker probing without introducing another unlink path.
- Added `--share-local-reads` and guarded `--read-socket` parsing while
  preserving positional initial dataset paths and default-off startup.
- Wrapped Python exits in `try/finally`/`atexit`, added idempotent Cocoa
  termination-delegate cleanup, and bridged terminal signals to Cocoa shutdown.
- Verified a real opted-in AppKit process served typed reads and removed its
  socket on signal-driven normal termination.

## Files Changed

- `labassistant/local_read_transport.py`
- `labassistant/desktop_read_sharing.py`
- `labassistant/desktop.py`
- `labassistant/ui/macos_window.py`
- `tests/test_local_read_transport.py`
- `tests/test_desktop_read_sharing.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/architecture/api-readiness.md`
- `docs/decisions/005-desktop-read-broker-lifecycle.md`
- `docs/status/current-state.md`
- `docs/prompts/066-implement-desktop-broker-lifecycle.md`

## Test Results

- Focused lifecycle/transport/desktop/client tests: 34 passed in 1.32s.
- Full suite: 265 passed in 3.02s.
- Markdown links validated across 95 documentation files.
- Real AppKit smoke: opted-in desktop served typed discovery, handled normal
  signal-driven Cocoa termination, stopped, and removed its owned socket.

## Remaining Work

- Audit macOS packaging, signing, sandbox, runtime-location, and entitlement
  requirements before enabling local read sharing in a packaged application.
