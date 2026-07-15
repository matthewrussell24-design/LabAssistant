from __future__ import annotations

from pathlib import Path

import pytest

from labassistant.context_engine import KnowledgeStore, default_knowledge_store_path
from labassistant.history import default_history_path, load_history, save_experiment
from labassistant.local_read_transport import default_socket_path
from labassistant.runtime_paths import (
    RuntimeMigrationError,
    RuntimePaths,
    discover_legacy_runtime_data,
    migrate_legacy_runtime_data,
    resolve_runtime_paths,
)


def test_macos_paths_are_platform_native_and_resolution_is_read_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = resolve_runtime_paths(environ={}, home=home, platform="darwin")

    assert paths.history_path == home / "Library/Application Support/LabAssistant/history/experiments.jsonl"
    assert paths.knowledge_store_path == home / "Library/Application Support/LabAssistant/memory/knowledge.sqlite"
    assert paths.socket_path == home / "Library/Caches/LabAssistant/runtime/read-api.sock"
    assert not home.exists()


def test_xdg_and_application_overrides_are_supported(tmp_path: Path) -> None:
    xdg = resolve_runtime_paths(
        environ={"XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache")},
        home=tmp_path / "home",
        platform="linux",
    )
    assert xdg.data_root == tmp_path / "data/LabAssistant"
    assert xdg.cache_root == tmp_path / "cache/LabAssistant"

    overridden = resolve_runtime_paths(
        environ={
            "LABASSISTANT_DATA_HOME": str(tmp_path / "custom-data"),
            "LABASSISTANT_CACHE_HOME": str(tmp_path / "custom-cache"),
        },
        home=tmp_path / "ignored",
        platform="darwin",
    )
    assert overridden.data_root == tmp_path / "custom-data"
    assert overridden.cache_root == tmp_path / "custom-cache"

    with pytest.raises(ValueError, match="absolute"):
        resolve_runtime_paths(environ={"LABASSISTANT_DATA_HOME": "relative"})


def test_implicit_defaults_are_resolved_lazily(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LABASSISTANT_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("LABASSISTANT_CACHE_HOME", str(tmp_path / "cache"))

    assert default_history_path() == tmp_path / "data/history/experiments.jsonl"
    assert default_knowledge_store_path() == tmp_path / "data/memory/knowledge.sqlite"
    assert default_socket_path() == tmp_path / "cache/runtime/read-api.sock"


def test_explicit_persistence_paths_remain_authoritative(tmp_path: Path) -> None:
    history = tmp_path / "explicit/history.jsonl"
    save_experiment([], "Explicit", history)
    assert [record.label for record in load_history(history)] == ["Explicit"]

    database = tmp_path / "explicit/knowledge.sqlite"
    store = KnowledgeStore(database)
    assert store.path == database
    assert database.exists()


def test_migration_copies_known_files_and_leaves_originals(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    old_history = source / ".labassistant_history/experiments.jsonl"
    old_knowledge = source / ".labassistant_memory/knowledge.sqlite"
    old_history.parent.mkdir(parents=True)
    old_knowledge.parent.mkdir(parents=True)
    old_history.write_text('{"id":"one"}\n', encoding="utf-8")
    old_knowledge.write_bytes(b"sqlite-data")
    destinations = _destinations(tmp_path / "new")

    receipt = migrate_legacy_runtime_data(source.resolve(), destinations=destinations)

    assert len(receipt.copied) == 2
    assert destinations.history_path.read_text(encoding="utf-8") == '{"id":"one"}\n'
    assert destinations.knowledge_store_path.read_bytes() == b"sqlite-data"
    assert old_history.exists() and old_knowledge.exists()
    assert destinations.history_path.parent.stat().st_mode & 0o777 == 0o700


def test_migration_requires_an_explicit_absolute_source(tmp_path: Path) -> None:
    with pytest.raises(RuntimeMigrationError, match="absolute"):
        discover_legacy_runtime_data(Path("relative"))
    with pytest.raises(RuntimeMigrationError, match="No legacy"):
        migrate_legacy_runtime_data(tmp_path.resolve(), destinations=_destinations(tmp_path / "new"))


def test_migration_rejects_symlinked_legacy_directories(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "experiments.jsonl").write_text("{}\n", encoding="utf-8")
    source.mkdir()
    (source / ".labassistant_history").symlink_to(actual, target_is_directory=True)

    with pytest.raises(RuntimeMigrationError, match="regular file"):
        discover_legacy_runtime_data(source.resolve())


def test_destination_conflict_prevents_partial_migration(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    for relative in (
        ".labassistant_history/experiments.jsonl",
        ".labassistant_memory/knowledge.sqlite",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy", encoding="utf-8")
    destinations = _destinations(tmp_path / "new")
    destinations.knowledge_store_path.parent.mkdir(parents=True)
    destinations.knowledge_store_path.write_text("current", encoding="utf-8")

    with pytest.raises(RuntimeMigrationError, match="destination"):
        migrate_legacy_runtime_data(source.resolve(), destinations=destinations)

    assert not destinations.history_path.exists()
    assert destinations.knowledge_store_path.read_text(encoding="utf-8") == "current"


def test_migration_rejects_symlinked_destination_parent(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    history = source / ".labassistant_history/experiments.jsonl"
    history.parent.mkdir(parents=True)
    history.write_text("legacy", encoding="utf-8")
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(RuntimeMigrationError, match="links"):
        migrate_legacy_runtime_data(source.resolve(), destinations=_destinations(linked))

    assert not (actual / "data/history/experiments.jsonl").exists()


def _destinations(root: Path) -> RuntimePaths:
    return RuntimePaths(
        data_root=root / "data",
        cache_root=root / "cache",
        history_path=root / "data/history/experiments.jsonl",
        knowledge_store_path=root / "data/memory/knowledge.sqlite",
        socket_path=root / "cache/runtime/read-api.sock",
    )
