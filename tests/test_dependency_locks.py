from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
LOCKS = ROOT / "requirements" / "locks"
PACKAGE = re.compile(r"^([a-z0-9][a-z0-9._-]*)==", re.MULTILINE)


def test_all_dependency_groups_have_hashed_macos_arm64_locks() -> None:
    for group in ("desktop", "streamlit", "build", "dev"):
        content = (LOCKS / f"{group}-py312-macos-arm64.txt").read_text(encoding="utf-8")
        assert "scripts/lock-dependencies" in content
        assert "--hash=sha256:" in content
        assert set(PACKAGE.findall(content))


def test_dependency_groups_preserve_surface_boundaries() -> None:
    desktop = _packages("desktop")
    streamlit = _packages("streamlit")
    build = _packages("build")
    dev = _packages("dev")

    assert {"pandas", "openpyxl", "xlrd", "pyobjc-core"} <= desktop
    assert not {"streamlit", "plotly", "pytest", "py2app"} & desktop
    assert {"streamlit", "plotly", "pandas"} <= streamlit
    assert not {"pyobjc-core", "pytest", "py2app"} & streamlit
    assert {"py2app", "pyobjc-core", "pandas"} <= build
    assert not {"streamlit", "plotly", "pytest"} & build
    assert {"py2app", "pytest", "streamlit", "plotly", "pyobjc-core", "pandas"} <= dev


def test_legacy_requirements_entrypoint_selects_full_lock() -> None:
    content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "-r requirements/locks/dev-py312-macos-arm64.txt" in content


def _packages(group: str) -> set[str]:
    content = (LOCKS / f"{group}-py312-macos-arm64.txt").read_text(encoding="utf-8")
    return {name.lower().replace("_", "-") for name in PACKAGE.findall(content)}
