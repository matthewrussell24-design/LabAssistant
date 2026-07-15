"""Platform-aware mutable runtime locations and explicit legacy-data import."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import Mapping
from uuid import uuid4


APP_DIRECTORY_NAME = "LabAssistant"
DATA_HOME_ENV = "LABASSISTANT_DATA_HOME"
CACHE_HOME_ENV = "LABASSISTANT_CACHE_HOME"


@dataclass(frozen=True)
class RuntimePaths:
    data_root: Path
    cache_root: Path
    history_path: Path
    knowledge_store_path: Path
    socket_path: Path


@dataclass(frozen=True)
class LegacyRuntimeData:
    source_root: Path
    history_path: Path | None
    knowledge_path: Path | None

    @property
    def available(self) -> bool:
        return self.history_path is not None or self.knowledge_path is not None


@dataclass(frozen=True)
class RuntimeMigrationReceipt:
    source_root: Path
    copied: tuple[tuple[Path, Path], ...]


class RuntimeMigrationError(RuntimeError):
    """Explicit legacy import could not proceed without weakening safety."""


def resolve_runtime_paths(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | str | None = None,
    platform: str | None = None,
) -> RuntimePaths:
    """Resolve locations without creating directories or importing UI frameworks."""
    values = os.environ if environ is None else environ
    user_home = Path(home).expanduser() if home is not None else Path.home()
    system = sys.platform if platform is None else platform

    data_override = values.get(DATA_HOME_ENV, "").strip()
    cache_override = values.get(CACHE_HOME_ENV, "").strip()
    if data_override:
        data_root = Path(data_override).expanduser()
        if not data_root.is_absolute():
            raise ValueError(f"{DATA_HOME_ENV} must be an absolute path")
    elif system == "darwin":
        data_root = user_home / "Library" / "Application Support" / APP_DIRECTORY_NAME
    else:
        xdg_data = values.get("XDG_DATA_HOME", "").strip()
        data_root = (
            Path(xdg_data).expanduser() / APP_DIRECTORY_NAME
            if xdg_data
            else user_home / ".local" / "share" / APP_DIRECTORY_NAME
        )

    if cache_override:
        cache_root = Path(cache_override).expanduser()
        if not cache_root.is_absolute():
            raise ValueError(f"{CACHE_HOME_ENV} must be an absolute path")
    elif system == "darwin":
        cache_root = user_home / "Library" / "Caches" / APP_DIRECTORY_NAME
    else:
        xdg_cache = values.get("XDG_CACHE_HOME", "").strip()
        cache_root = (
            Path(xdg_cache).expanduser() / APP_DIRECTORY_NAME
            if xdg_cache
            else user_home / ".cache" / APP_DIRECTORY_NAME
        )

    return RuntimePaths(
        data_root=data_root,
        cache_root=cache_root,
        history_path=data_root / "history" / "experiments.jsonl",
        knowledge_store_path=data_root / "memory" / "knowledge.sqlite",
        socket_path=cache_root / "runtime" / "read-api.sock",
    )


def discover_legacy_runtime_data(source_root: Path | str) -> LegacyRuntimeData:
    """Inspect only an explicitly supplied root; never scan the process CWD."""
    root = _safe_source_root(source_root)
    history = _safe_legacy_file(root / ".labassistant_history" / "experiments.jsonl")
    knowledge = _safe_legacy_file(root / ".labassistant_memory" / "knowledge.sqlite")
    return LegacyRuntimeData(root, history, knowledge)


def migrate_legacy_runtime_data(
    source_root: Path | str,
    *,
    destinations: RuntimePaths | None = None,
) -> RuntimeMigrationReceipt:
    """Atomically copy explicitly selected legacy data without deleting sources."""
    legacy = discover_legacy_runtime_data(source_root)
    if not legacy.available:
        raise RuntimeMigrationError("No legacy LabAssistant data was found")
    paths = destinations or resolve_runtime_paths()
    transfers = tuple(
        (source, target)
        for source, target in (
            (legacy.history_path, paths.history_path),
            (legacy.knowledge_path, paths.knowledge_store_path),
        )
        if source is not None
    )
    for _, target in transfers:
        _validate_destination(target)
    conflicts = [target for _, target in transfers if target.exists() or target.is_symlink()]
    if conflicts:
        raise RuntimeMigrationError("A destination already contains LabAssistant data")

    copied: list[tuple[Path, Path]] = []
    temporary: list[Path] = []
    try:
        for source, target in transfers:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.parent.chmod(0o700)
            temp_path = target.with_name(f".{target.name}.{uuid4().hex}.migrating")
            temporary.append(temp_path)
            shutil.copy2(source, temp_path, follow_symlinks=False)
            os.replace(temp_path, target)
            copied.append((source, target))
    except Exception as exc:
        for temp_path in temporary:
            temp_path.unlink(missing_ok=True)
        for _, target in copied:
            target.unlink(missing_ok=True)
        raise RuntimeMigrationError("Legacy data import failed") from exc
    return RuntimeMigrationReceipt(legacy.source_root, tuple(copied))


def _safe_source_root(source_root: Path | str) -> Path:
    supplied = Path(source_root).expanduser()
    if not supplied.is_absolute():
        raise RuntimeMigrationError("Legacy source must be an absolute directory")
    if supplied.is_symlink() or not supplied.is_dir():
        raise RuntimeMigrationError("Legacy source must be a real directory")
    resolved = supplied.resolve(strict=True)
    info = resolved.stat()
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeMigrationError("Legacy source must belong to the current user")
    return resolved


def _safe_legacy_file(path: Path) -> Path | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise RuntimeMigrationError("Legacy data must be a regular file")
    info = path.stat()
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeMigrationError("Legacy data must belong to the current user")
    return path


def _validate_destination(path: Path) -> None:
    if not path.is_absolute():
        raise RuntimeMigrationError("Migration destinations must be absolute")
    for parent in path.parents:
        if parent.is_symlink():
            raise RuntimeMigrationError("Migration destinations cannot traverse links")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("migrate", choices=("migrate",))
    parser.add_argument("--from", dest="source_root", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = migrate_legacy_runtime_data(args.source_root)
    for source, destination in receipt.copied:
        print(f"Copied {source} -> {destination}")
    print("Legacy originals were left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
