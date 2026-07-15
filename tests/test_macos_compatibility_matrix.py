from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_uses_explicit_clean_arm64_matrix() -> None:
    workflow = (ROOT / ".github/workflows/macos-compatibility.yml").read_text()

    assert "runner: macos-14" in workflow
    assert "runner: macos-26" in workflow
    assert 'macos: "14"' in workflow
    assert 'macos: "26"' in workflow
    assert "scripts/qualify-macos-compatibility" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "fail-fast: false" in workflow


def test_matrix_runner_covers_required_qualification_boundaries() -> None:
    runner = (ROOT / "scripts/qualify-macos-compatibility").read_text()

    for command in (
        "scripts/build-macos-qualification",
        "scripts/inspect-macos-qualification",
        "scripts/smoke-macos-qualification",
    ):
        assert command in runner
    assert "LABASSISTANT_EXPECTED_MACOS_MAJOR" in runner
    assert "run_persistence_smoke" in runner
    assert "second_history_count" in runner
    assert 'open -n "$APP"' in runner
    assert "summary.env" in runner
