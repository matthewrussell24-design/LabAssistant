from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _runtime() -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in (ROOT / "packaging/macos/runtime.env").read_text().splitlines()
        if line and not line.startswith("#")
    )


def test_controlled_runtime_is_exactly_pinned() -> None:
    runtime = _runtime()

    assert runtime["PYTHON_RUNTIME_VERSION"] == "3.12.13"
    assert runtime["PYTHON_RUNTIME_BUILD"] == "20260623"
    assert runtime["PYTHON_RUNTIME_ARCH"] == "arm64"
    assert runtime["PYTHON_RUNTIME_MIN_MACOS"] == "11.0"
    assert runtime["BUNDLE_MIN_MACOS"] == "14.0"
    assert runtime["PYTHON_RUNTIME_URL"].startswith(
        "https://releases.astral.sh/github/python-build-standalone/releases/download/"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", runtime["PYTHON_RUNTIME_SHA256"])


def test_qualification_build_uses_verified_runtime_and_declared_floor() -> None:
    build = (ROOT / "scripts/build-macos-qualification").read_text()
    inspect = (ROOT / "scripts/inspect-macos-qualification").read_text()
    setup = (ROOT / "packaging/macos/setup.py").read_text()

    assert "source \"$ROOT_DIR/packaging/macos/runtime.env\"" in build
    assert "shasum -a 256 --check --status" in build
    assert 'PYTHON="$RUNTIME_ROOT/python/bin/python3.12"' in build
    assert "/opt/homebrew" not in build
    assert 'os.environ["LABASSISTANT_MIN_MACOS"]' in setup
    assert "LSMinimumSystemVersion" in setup
    assert "Bundle requires macOS" in inspect
