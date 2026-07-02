from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from labassistant.importers.file_classifier import (
    CORRELOGRAM,
    INTENSITY_DISTRIBUTION,
    SUMMARY_EXPORT,
    UNKNOWN,
    ClassifiedFile,
)


@dataclass
class LotFileGroup:
    lot_key: str
    lot: str
    files: list[ClassifiedFile] = field(default_factory=list)

    @property
    def summary_files(self) -> list[ClassifiedFile]:
        return self._files_by_type(SUMMARY_EXPORT)

    @property
    def intensity_files(self) -> list[ClassifiedFile]:
        return self._files_by_type(INTENSITY_DISTRIBUTION)

    @property
    def correlogram_files(self) -> list[ClassifiedFile]:
        return self._files_by_type(CORRELOGRAM)

    @property
    def unknown_files(self) -> list[ClassifiedFile]:
        known_duplicates = self.summary_files[1:] + self.intensity_files[1:] + self.correlogram_files[1:]
        return self._files_by_type(UNKNOWN) + known_duplicates

    @property
    def status(self) -> str:
        statuses = []
        if not self.summary_files:
            statuses.append("Missing summary")
        if not self.intensity_files:
            statuses.append("Missing intensity distribution")
        if not self.correlogram_files:
            statuses.append("Missing correlogram")
        if self.unknown_files:
            statuses.append("Unknown files")
        return ", ".join(statuses) if statuses else "Complete"

    def _files_by_type(self, file_type: str) -> list[ClassifiedFile]:
        return [classified for classified in self.files if classified.file_type == file_type]


def group_files_by_lot(classified_files: list[ClassifiedFile]) -> list[LotFileGroup]:
    groups: dict[str, LotFileGroup] = {}
    for classified_file in classified_files:
        lot_key = detect_lot_key(classified_file)
        groups.setdefault(lot_key, LotFileGroup(lot_key=lot_key, lot=display_lot(lot_key))).files.append(classified_file)
    return sorted(groups.values(), key=lambda group: _lot_sort_key(group.lot_key))


def detect_lot_key(classified_file: ClassifiedFile) -> str:
    candidates = [classified_file.file_name]
    if classified_file.parsed_result is not None:
        candidates.append(classified_file.parsed_result.name)
        sample_name = classified_file.parsed_result.metadata.get("Sample Name") or classified_file.parsed_result.metadata.get("Sample")
        if sample_name:
            candidates.append(sample_name)

    for candidate in candidates:
        lot = _extract_lot_from_text(candidate)
        if lot:
            return lot

    return _fallback_lot_key(classified_file.file_name)


def display_lot(lot_key: str) -> str:
    lot_number = re.fullmatch(r"lot_(\d+)", lot_key)
    if lot_number:
        return f"Lot {int(lot_number.group(1))}"
    return lot_key


def preview_rows(groups: list[LotFileGroup]) -> list[dict[str, str]]:
    return [
        {
            "Lot": group.lot,
            "Summary file": _first_file_name(group.summary_files),
            "Intensity file": _first_file_name(group.intensity_files),
            "Correlogram file": _first_file_name(group.correlogram_files),
            "Status": group.status,
        }
        for group in groups
    ]


def _extract_lot_from_text(value: str) -> str | None:
    text = Path(value).stem

    # Project convention: lot-like sample IDs such as 446-01, Lot 446-01,
    # and Lyo 446-01 use the suffix as the lot number.
    sample_match = re.search(r"\b(\d{3,})[-_ ]0*(\d{1,3})\b", text)
    if sample_match:
        return f"lot_{int(sample_match.group(2))}"

    lot_match = re.search(r"\blot\s*[-_ ]*0*(\d+)\b", text, re.IGNORECASE)
    if lot_match:
        return f"lot_{int(lot_match.group(1))}"

    return None


def _first_file_name(files: list[ClassifiedFile]) -> str:
    return files[0].file_name if files else ""


def _fallback_lot_key(file_name: str) -> str:
    return Path(file_name).stem


def _lot_sort_key(lot_key: str) -> tuple[str, int, str]:
    lot_number = re.fullmatch(r"lot_(\d+)", lot_key)
    if lot_number:
        return ("lot", int(lot_number.group(1)), lot_key)
    return (lot_key.lower(), 0, lot_key)
