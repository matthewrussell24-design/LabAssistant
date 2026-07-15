# 004 - Local Read-Only Transport

Status: Accepted
Date: 2026-07-15
Related Prompt: `docs/prompts/062-select-local-read-transport.md`

## Context

LabAssistant has a stable `1.0` contract for seven read operations, but only as
an in-process Python boundary. A first transport must serve the native desktop,
CLI tools, and future local agents without making the scientific core depend on
a client, treating loopback as identity, or introducing remote deployment.

## Decision

Use a Unix-domain stream socket with newline-delimited JSON for the first local
read-only transport. The initial adapter will be an explicitly started,
foreground broker owned by the current OS user. It will use the Python standard
library, expose only the stable seven-read allowlist, and call
`invoke_candidate_read()` without duplicating application behavior.

The socket will live in a user-private runtime directory (`0700`) and be
owner-only (`0600`). The broker must verify peer credentials and fail closed
when it cannot establish the peer's user identity. It will derive
`LocalReadAccessContext` itself:

- `subject`: canonical local OS user identity derived from the peer;
- `client_id`: a fixed broker identity approved by local policy;
- `origin`: always `local`;
- `scopes`: server-configured read scopes, never request fields.

Requests cannot provide or override identity, scopes, paths, stores, or other
in-process collaborators. The broker will never bind TCP, expose writes, or run
as a persistent login daemon in its first implementation.

## Threat Model

The first adapter protects against network access, other local OS users, stale
or incorrectly owned socket paths, malformed/oversized frames, and accidental
exposure of non-public registry operations. It assumes the current OS account
and LabAssistant installation are trusted.

It does **not** protect against a malicious process already executing as the
same OS user. Socket file modes and peer credentials identify an OS security
principal, not a distinct application. Per-client credentials, sandbox
attestation, remote authentication, and multi-user service isolation are later
security decisions. If the product must resist same-user processes, this
transport may remain useful but the access mechanism must be upgraded before
that deployment is approved.

## Framing and Error Boundary

Each UTF-8 line is one JSON object. A transport frame wraps, but does not alter,
the stable application envelope:

```json
{"transport_version":"1","request_id":"01...","contract_version":"1.0","capability":"list_experiments","parameters":{"limit":25,"offset":0}}
```

```json
{"transport_version":"1","request_id":"01...","response":{"api_version":"1.0","capability":"list_experiments","data":{},"ok":true}}
```

Malformed JSON, invalid UTF-8, missing framing fields, unsupported transport
versions, and frame-size violations are transport errors. Valid requests use
the stable application success/error envelope unchanged, including
`access_denied`, `invalid_input`, and `internal_failure`. Transport messages
must not include exception text or local filesystem details.

Exact size, timeout, concurrency, socket-location, and stale-socket rules must
be constants with boundary tests in the implementation task; they are not part
of the application `1.0` schema.

## Alternatives

| Option | Strength | Why it is not first |
| --- | --- | --- |
| In-process plugin calls | Smallest implementation and already proven | Couples clients to Python and one process; independent CLI/agent clients cannot share a stable process boundary |
| Unix-domain IPC | Local-only namespace, filesystem ownership, no port, process-independent | Selected; Unix-specific and still needs lifecycle/framing code |
| Loopback HTTP | Familiar tooling and broad client compatibility | A port is not identity; adds discovery, authorization, framework, browser/CORS, and deployment questions before they are needed |

## Lifecycle and Deployment Consequences

- The first broker is foreground and explicit: its parent owns startup,
  shutdown, logs, and socket cleanup.
- Only one broker may own a socket path. Startup must refuse unsafe ownership
  and remove a stale socket only after proving the path is owner-controlled and
  no server is listening.
- Normal shutdown removes the socket. Abrupt termination is handled by the
  guarded stale-socket startup path.
- Desktop-managed startup may follow after the standalone broker is proven;
  the application contract and framing must remain client-neutral.
- A packaged app must choose an application-support/runtime location and macOS
  sandbox entitlements deliberately. This ADR does not claim packaging is done.
- Windows or remote clients require a separate transport decision, not silent
  fallback to loopback HTTP.

## Implementation Sequence and Gate

1. Prove peer-credential retrieval on supported macOS/Python and fail closed on
   unsupported platforms.
2. Add transport frame parsing/serialization with strict allowlists and bounds.
3. Add broker-owned access-context mapping and approve its fixed client ID in
   local policy.
4. Add a foreground server lifecycle and a tiny diagnostic CLI client.
5. Test all seven reads, all stable application errors, malformed/oversized
   frames, peer rejection, stale sockets, and cleanup.
6. Run a desktop/CLI integration smoke before considering desktop-managed
   startup or a future agent SDK.

Decision: **go** for that minimal adapter, conditional on step 1. If supported
macOS/Python cannot reliably derive and verify peer identity, stop rather than
substituting a request-supplied identity or loopback listener.

## Consequences

- The stable application contract stays transport-neutral.
- No new runtime dependency or network listener is introduced by this decision.
- The design supports independent local clients while keeping the first
  security claim intentionally narrow.
- Writes, autonomous agents, instrument control, remote access, background
  services, and authentication beyond the local OS principal remain excluded.
