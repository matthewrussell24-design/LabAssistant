# Dependency Groups

Human-maintained `.in` files define direct dependencies; generated locks record
the complete wheel-only Python 3.12 macOS arm64 environment with SHA-256 hashes.

| Group | Purpose | Deliberately excludes |
| --- | --- | --- |
| `desktop` | Shared science runtime plus Cocoa/WebKit native shell | Streamlit, Plotly, pytest, py2app |
| `streamlit` | Shared science runtime plus Streamlit/Plotly shell | PyObjC, pytest, py2app |
| `build` | Desktop runtime plus py2app bundle tooling | Streamlit, Plotly, pytest |
| `dev` | Complete contributor and packaging-spike environment | Nothing from the other groups |

Install one group with pip's hash verification:

```bash
python3.12 -m pip install --require-hashes \
  -r requirements/locks/desktop-py312-macos-arm64.txt
```

`pip install -r requirements.txt` remains the compatibility command for the
complete `dev` lock. Regenerate every lock with `scripts/lock-dependencies`.
The script requires `uv`, resolves only binary distributions for the declared
target, and writes a stable generation command into each lock header.

These files qualify dependency resolution, not a bundle. Dynamic-import and
package-data discovery still belongs to the py2app build and smoke-test task.
