from pathlib import Path

from labassistant.packaging_smoke import run_packaging_smoke


def test_packaging_smoke_exercises_science_and_platform_paths(
    monkeypatch, tmp_path: Path
) -> None:
    root = Path(__file__).parents[1]
    monkeypatch.setenv("LABASSISTANT_DATA_HOME", str(tmp_path / "Application Support"))
    monkeypatch.setenv("LABASSISTANT_CACHE_HOME", str(tmp_path / "Caches"))

    result = run_packaging_smoke(root)

    assert result["status"] == "ok"
    assert result["dls_measurements"] > 0
    assert result["chromatography_measurements"] > 0
    assert result["openlab_measurements"] > 0
    assert result["socket_created"] is False
