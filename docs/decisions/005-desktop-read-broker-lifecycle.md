# 005 - Desktop Read Broker Lifecycle

Status: Accepted
Date: 2026-07-15
Related Prompt: `docs/prompts/065-decide-desktop-broker-lifecycle.md`

## Context

The foreground Unix-domain broker and typed client are complete, but users must
start the broker separately. The native AppKit desktop could own the broker
during normal human use. Doing so without explicit consent would turn a local
window launch into a surprise IPC listener and blur responsibility for startup,
status, collision recovery, and shutdown.

## Decision

The desktop may own the local read broker only when launched with an explicit
`--share-local-reads` flag. The default desktop launch remains unchanged: no
socket is created. Consent is per launch, is not persisted, and does not imply
remote access, writes, an agent runtime, or future automatic startup.

The desktop process owns the lifecycle, while a dedicated non-AppKit worker
thread serves requests. Scientific reads continue to use application services;
the broker never reads WebKit, window, controller, or session state. The
standalone `scripts/run-read-broker` workflow remains supported and is not
replaced by desktop ownership.

## Alternatives

| Model | Strength | Decision |
| --- | --- | --- |
| Separate foreground broker only | Clearest ownership and already proven | Retain as the operational fallback, but it requires a second command |
| Explicit desktop launch flag | Clear per-run consent, process-bounded lifetime, no UI preference migration | Selected for the first integration |
| In-app opt-in preference | Discoverable and capable of richer status | Defer until packaging, preference storage, and sandbox behavior are defined |
| Automatic desktop startup | Lowest friction | Rejected; creates IPC without user intent and obscures failures |
| Persistent login daemon | Available without the desktop | Rejected; expands installation, update, audit, and shutdown scope |

## Consent and Status

- `scripts/run-desktop` and `python -m labassistant.desktop` accept
  `--share-local-reads`; absence means disabled.
- Initial file paths remain positional arguments and cannot accidentally enable
  sharing.
- When requested, startup reports one concise status to stderr: owned and
  available, compatible external broker already available, or unavailable with
  a safe reason. It may include the configured socket path but never scientific
  data or exception internals.
- The desktop window still opens if sharing is unavailable. A failed optional
  read-sharing feature must not block the human analysis workspace.
- No preference is saved, no checkbox silently survives restart, and the flag
  does not modify the standalone broker.

## Ownership and Collision Rules

1. The desktop first attempts the existing guarded `LocalReadBroker.start()`.
2. If it acquires the socket, it is the owner and is solely responsible for
   serving and cleanup.
3. If an active socket already exists, the desktop probes it with the typed
   client discovery call. A compatible `1.0` seven-read broker satisfies the
   user's sharing request, but remains externally owned. The desktop must not
   unlink or stop it.
4. An incompatible broker, unsafe path, unverifiable peer, or failed probe is
   reported as unavailable. The desktop continues without sharing and does not
   replace the path.
5. Stale socket cleanup remains exclusively governed by the owner/mode/type
   checks in `LocalReadBroker`; desktop code must not add another unlink path.

## Threading and Shutdown

- AppKit remains on the main thread.
- The broker runs on one dedicated worker with cooperative stop state; it must
  not touch AppKit objects.
- `LocalReadBroker` must gain a bounded way to stop an already-started accept
  loop. Closing the listener unblocks acceptance, and the owner joins the
  worker with a finite timeout.
- Desktop startup wraps `run_native_workspace()` in `try/finally`. Normal window
  close, AppKit termination, startup failure after acquisition, `KeyboardInterrupt`,
  and unhandled application errors all execute owner cleanup.
- Cleanup is idempotent. Only a desktop-owned socket is removed; an externally
  owned compatible broker is untouched.
- A worker that cannot stop within the bound is reported, not hidden. The
  implementation must prove the process still terminates without leaving an
  owned socket.

## Diagnostics and Failure Mapping

Desktop ownership status is operational metadata, separate from the stable
application contract. Startup/collision errors must use bounded categories such
as `owned`, `external`, `unsafe_path`, `incompatible`, `unavailable`, and
`shutdown_failed`. They must not change stable application error codes or leak
filesystem contents, peer details, or exception text.

The first implementation does not add a new workspace panel. A future in-app
control must show the same ownership state and require a separate reviewed
decision about persistence and live enable/disable behavior.

## Packaging and Sandbox Consequences

- The current development socket location is not automatically approved for a
  packaged or sandboxed application.
- Before enabling this flag in a packaged build, validate socket visibility,
  runtime-directory ownership, path-length limits, signing, sandbox rules, and
  whether external clients require an App Group or other entitlement.
- If sandboxing prevents the same security claim, packaged sharing stays off;
  it must not fall back to loopback HTTP or a broader directory.
- No login item, launch agent, installer service, or firewall rule is introduced.

## Implementation Sequence and Gate

1. Add a small lifecycle owner independent of AppKit with states for disabled,
   owned, external, and unavailable.
2. Add cooperative broker stop/unblock behavior with idempotent cleanup tests.
3. Add desktop argument parsing that separates the flag from initial file paths.
4. Start ownership before the AppKit run loop and close it in an outer
   `try/finally`; keep the worker free of UI imports.
5. Add compatible collision probing through `LocalReadClient.describe_platform()`
   and safe stderr status.
6. Test default-off behavior, owned lifecycle, compatible external collision,
   unsafe/incompatible collision, startup failure, shutdown, and unchanged
   positional file launch.
7. Run a real AppKit launch/close smoke and a typed external read while the
   opt-in desktop owns the socket.

Decision: **go** for this bounded opt-in integration. Do not implement in-app
preference persistence or enable the feature in a packaged build until their
separate gates are satisfied.

## Consequences

- Normal desktop behavior remains unchanged and listener-free.
- Opt-in sharing has visible, process-bounded ownership and deterministic cleanup.
- Existing standalone broker users remain compatible.
- Desktop UI state and scientific core boundaries remain independent of IPC.
- Hidden startup, persistent services, remote transport, writes, autonomous
  agents, and instrument control remain excluded.

## Task 066 Implementation

The opt-in lifecycle is implemented with an AppKit-independent owner and a
cooperative broker worker. The default launch remains socket-free. Compatible
external brokers are detected through typed discovery and never closed by the
desktop. Cocoa's termination path does not reliably return through the Python
run-loop call, so the application delegate invokes the same idempotent cleanup
used by the outer `try/finally`; an `atexit` registration provides another safe
Python exit path. Terminal signals are bridged into normal Cocoa termination.
