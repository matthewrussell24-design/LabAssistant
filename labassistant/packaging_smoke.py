"""Bounded scientific/runtime smoke used only by local bundle qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

from labassistant.application import analyze_dls_dataset
from labassistant.context_engine import KnowledgeStore
from labassistant.history import load_history, save_experiment
from labassistant.importers.chromatography import parse_chromatography_csv
from labassistant.importers.openlab_olax import inspect_openlab_olax
from labassistant.runtime_paths import resolve_runtime_paths


def run_packaging_smoke(source_root: Path | str) -> dict[str, object]:
    root = Path(source_root).resolve(strict=True)
    dls_paths = [
        root / "tests/fixtures/Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
        root / "tests/fixtures/Size Distribution by Intensity Lot 1.xlsx",
        root / "tests/fixtures/Correlogram lot 1.xlsx",
    ]
    dls_result = analyze_dls_dataset(dls_paths, label="Packaged qualification")
    chromatography = parse_chromatography_csv(
        root / "sample_data/chromatography/mass_balance_demo.csv"
    )

    paths = resolve_runtime_paths()
    olax_path = paths.data_root / "qualification/openlab-smoke.olax"
    olax_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(olax_path, "w") as archive:
        archive.writestr(
            "Sequence/sequence.xml",
            "<Sequence><SequenceName>Qualification</SequenceName>"
            "<Injection><InjectionOrder>1</InjectionOrder>"
            "<SampleName>Sample A</SampleName><Method>HPLC</Method>"
            "</Injection></Sequence>",
        )
        archive.writestr(
            "Data/Injection_001/signal.ch",
            "time_min,intensity\n0.0,10\n0.5,15\n1.0,12\n",
        )
    openlab = inspect_openlab_olax(olax_path)
    record = save_experiment([], "Packaged qualification")
    history = load_history()
    knowledge = KnowledgeStore()

    if paths.socket_path.exists():
        raise RuntimeError("default launch unexpectedly created a read socket")
    if not paths.history_path.is_file() or not paths.knowledge_store_path.is_file():
        raise RuntimeError("packaged persistence did not use resolved runtime paths")
    if not any(item.id == record.id for item in history):
        raise RuntimeError("packaged history could not be reopened")

    return {
        "status": "ok",
        "dls_measurements": len(dls_result.measurements),
        "chromatography_measurements": len(chromatography),
        "openlab_measurements": len(openlab.measurements),
        "history_path": str(paths.history_path),
        "knowledge_path": str(knowledge.path),
        "socket_created": paths.socket_path.exists(),
    }


def main() -> int:
    source_root = os.environ.get("LABASSISTANT_QUALIFICATION_SOURCE")
    if not source_root:
        raise RuntimeError("LABASSISTANT_QUALIFICATION_SOURCE is required")
    print(json.dumps(run_packaging_smoke(source_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
