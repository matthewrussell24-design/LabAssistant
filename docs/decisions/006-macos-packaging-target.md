# 006 - First macOS Packaging Target

Status: Accepted
Date: 2026-07-15
Related Prompt: `docs/prompts/067-audit-macos-packaging-readiness.md`

## Decision Summary

LabAssistant's first distributable desktop target is a **standalone arm64 macOS
app, signed with Developer ID, hardened, notarized, and distributed outside the
Mac App Store without App Sandbox**. Use py2app because it is the packaging path
recommended by PyObjC. The first implementation milestone is an ad-hoc-signed
local qualification bundle; that bundle is not a release and must never be
described as distributable.

Local read sharing remains default-off in every bundle. A sandboxed/App Store
target and universal2 support are later qualification tracks, not silent build
options.

## Current Readiness

| Area | Current evidence | Decision |
| --- | --- | --- |
| Host/runtime | Python 3.12.13 and installed binaries are arm64 | First target is arm64 only |
| Native UI | PyObjC Cocoa/WebKit 12.2.1; AppKit/WKWebView smoke passes | Bundle the native entry point |
| Packaging tool | py2app is not installed | Pin it after a focused compatibility spike |
| Dependencies | broad `requirements.txt` is mostly unpinned | Split and lock desktop runtime/build inputs |
| Persistence | task 068 routes history and memory through a pure Application Support resolver | Runtime-path gate passed |
| Socket | task 068 routes the owner-only path through the same Caches contract | Keep default-off; qualify separately |
| Resources | workspace HTML is an embedded Python constant | Keep mutable data out of `Contents/Resources` |
| Tooling | Xcode 26.6, `notarytool`, `stapler`, and `codesign` exist | Scripted notarization is possible |
| Credentials | zero valid signing identities are installed | Distribution signing is currently blocked |

## Why This Distribution Model

Apple requires Developer ID signing, hardened runtime, secure timestamps, and
notarization for contemporary software distributed outside the Mac App Store.
App Sandbox is optional for that route and required for Mac App Store review.
Direct Developer ID distribution is therefore the smallest honest first
boundary for the existing local scientific-file workflow.

A sandboxed target is deferred because it changes more than signing:

- selected inputs need user-selected-file entitlements and security-scoped
  lifecycle handling;
- persistent state moves into the sandbox container;
- external Unix-domain clients require a reviewed App Group/container and
  signed-client story;
- current arbitrary local CLI clients do not automatically belong to that App
  Group.

Apple documents App Groups as enabling Unix-domain IPC between sandboxed apps
and between sandboxed and nonsandboxed apps. Until that client/entitlement
design exists, packaged sandbox sharing remains off.

## Bundle and Runtime Layout

The bundle is immutable after signing:

```text
LabAssistant.app/
  Contents/
    Info.plist
    MacOS/LabAssistant
    Frameworks/              bundled Python/native dependencies
    Resources/               Python modules and immutable package resources
```

Mutable user state is outside the bundle:

```text
~/Library/Application Support/LabAssistant/
  history/experiments.jsonl
  memory/knowledge.sqlite

~/Library/Caches/LabAssistant/
  runtime/read-api.sock      only during explicit sharing
  ...                        discardable future caches
```

The implementation uses the pure `labassistant.runtime_paths` resolver rather
than hard-coded home strings. Resolution is lazy and side-effect free, and
explicit caller paths remain authoritative. For a future sandboxed build,
Foundation directory APIs resolve inside its container. Existing CWD-relative
development data moves only through `scripts/migrate-runtime-data --from` as a
copy-only operation that rejects links and conflicts and preserves originals.

Files selected through `NSOpenPanel` remain external user documents. The app
reads them in place and never copies raw laboratory data into the app bundle.

## Dependency and Resource Boundary

The native bundle needs the LabAssistant package, Python 3.12 runtime, PyObjC
Cocoa/WebKit, pandas/numpy, openpyxl, xlrd, and their actual transitive runtime
dependencies. Exclude Streamlit, Plotly, pytest, and development-only packages
unless a frozen-import trace proves they are required by the native entry point.

Do not rely only on static imports. py2app notes that dynamic imports and
in-package data can require explicit packages, includes, or recipes. The
qualification build must exercise CSV, XLS, XLSX, DLS, chromatography, OpenLab
`.olax`, history, SQLite memory, WebKit, and opt-in local reads before its bundle
manifest is accepted.

The workspace document is currently embedded Python text. If it later becomes
a file tree, immutable assets belong in `Contents/Resources` and must be located
through bundle-resource APIs, never the current working directory.

## Identity, Signing, and Entitlements

- Select a team-owned reverse-DNS bundle identifier before signing; a
  development placeholder is not a release identity.
- Sign all nested Mach-O code and the outer app with a Developer ID Application
  certificate, hardened runtime, and secure timestamp.
- Start with no App Sandbox entitlement and no hardened-runtime exceptions.
- Do not add `get-task-allow`, disable library validation, unsigned executable
  memory, or JIT entitlements unless a failing signed test proves the minimum
  required exception and records its rationale.
- Submit with `notarytool`, inspect its log, staple the ticket, then verify
  signatures, Gatekeeper assessment, and stapling offline.
- Store credentials in Keychain/CI secret facilities, never repository files or
  command transcripts.

This machine has no valid signing identity. It can build and test a local
qualification bundle but cannot complete the distribution gate.

## Architecture and Compatibility

The first bundle is arm64. universal2 requires a universal2 Python runtime and
compatible slices for every native wheel; it is a separate matrix entry. Do not
merge independently built architecture-specific bundles with `lipo`.

The minimum supported macOS version is not yet frozen. Inspect deployment
targets for Python and every bundled Mach-O dependency, choose the highest
required minimum, then verify clean machines. Until that matrix exists, only
the build/test host is qualified and development artifacts must say so.

## Verification Matrix

| Stage | Required checks |
| --- | --- |
| Local standalone bundle | clean non-alias build; Finder and CLI launch; no `.venv` dependency; default creates no socket |
| Scientific workflow | NSOpenPanel; DLS end to end; CSV/XLS/XLSX; chromatography/OpenLab; history reopen; SQLite memory |
| Runtime layout | only approved Application Support/Caches writes; read-only app bundle; paths with spaces; fresh profile |
| Native/runtime audit | enumerate Mach-O architectures; reject missing/foreign slices and absolute build-host library paths |
| Opt-in reads | default off; explicit typed read; same-user modes; Cocoa termination removes owned socket |
| Signed qualification | hardened Developer ID signatures valid recursively; no unapproved entitlements; clean-machine launch |
| Notarized candidate | accepted log reviewed; ticket stapled; `spctl` and `stapler validate` pass; offline Gatekeeper launch |
| Compatibility | declared minimum and current macOS on clean arm64 machines; upgrade preserves user state |

## Implementation Sequence and Gates

1. Centralize Application Support, Caches, history, memory, and socket paths;
   preserve explicit test/CLI injection and define legacy-data migration.
2. Split runtime, desktop-build, Streamlit, and development dependencies; create
   a reproducible lock with hashes or equivalent reviewed mechanism.
3. Add a minimal py2app entry/configuration with a non-release development
   bundle ID and arm64 standalone build (never alias mode for qualification).
4. Add bundle inspection and smoke scripts for imports, native slices, linked
   paths, writable locations, default-off IPC, and representative workflows.
5. Freeze the deployment target from the Mach-O audit and clean-machine matrix.
6. Obtain the team-owned bundle ID and Developer ID Application identity; sign
   with hardened runtime and secure timestamp using minimal entitlements.
7. Submit with `notarytool`, review logs, staple, assess, and archive provenance.

Decision: **go** for steps 1–4 and an arm64 local qualification bundle. **No-go**
for calling any artifact distributable until steps 5–7 pass. **No-go** for App
Sandbox, Mac App Store, universal2, or packaged local-read sharing until their
separate matrices and entitlement designs pass.

## Alternatives

- **Unsigned/ad-hoc app as the product:** rejected; useful only as a local build
  stage and misleading for Gatekeeper distribution.
- **Mac App Store first:** rejected; sandbox, file access, IPC, and review scope
  are larger than the current product boundary.
- **PyInstaller first:** not selected because PyObjC recommends py2app. Revisit
  only if a bounded py2app spike fails with a documented blocker.
- **Universal2 first:** rejected until Python and every native wheel have
  qualified dual slices.
- **Installer package first:** rejected; a notarized app in a ZIP is sufficient
  for the first drag-to-Applications distribution.

## Authoritative References

- [Apple: Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Apple: Preparing your app for distribution](https://developer.apple.com/documentation/xcode/preparing-your-app-for-distribution)
- [Apple: Configuring the macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox)
- [Apple: Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)
- [Apple: Configuring App Groups](https://developer.apple.com/documentation/xcode/configuring-app-groups)
- [Apple: Application Support directory](https://developer.apple.com/documentation/foundation/url/applicationsupportdirectory)
- [PyObjC: Building applications with py2app](https://pyobjc.readthedocs.io/en/latest/core/intro.html#building-applications)
- [py2app: Recipes and package-data constraints](https://py2app.readthedocs.io/en/stable/recipes.html)

## Consequences

- Packaging begins with runtime paths and reproducibility, not wrapping the
  current virtual environment wholesale.
- The first distribution target is narrow: arm64, Developer ID, notarized, and
  non-sandboxed.
- Local qualification can proceed without credentials; distribution cannot.
- Sandbox and universal support remain explicit future work.
