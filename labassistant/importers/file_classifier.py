from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from labassistant.importers.dls import ParsedDLSResult, parse_dls_upload, read_uploaded_text

SUMMARY_EXPORT = "summary/statistics export"
INTENSITY_DISTRIBUTION = "size distribution by intensity"
CORRELOGRAM = "correlogram"
UNKNOWN = "unknown"


@dataclass
class ClassifiedFile:
    file: object
    file_name: str
    file_type: str
    parsed_result: ParsedDLSResult | None = None
    source_text: str = ""
    error: str | None = None


def classify_uploaded_file(uploaded_file) -> ClassifiedFile:
    """Classify one uploaded DLS export using filename hints plus parsed content."""
    file_name = uploaded_file.name
    name_hint = _classify_from_name(file_name)
    source_text = _safe_read_text(uploaded_file)

    parsed_result = None
    parse_error = None
    try:
        parsed_result = parse_dls_upload(uploaded_file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ImportError, ValueError) as error:
        parse_error = str(error)

    content_hint = _classify_from_parsed_result(parsed_result) or _classify_from_text(source_text)
    file_type = name_hint or content_hint or UNKNOWN

    return ClassifiedFile(
        file=uploaded_file,
        file_name=file_name,
        file_type=file_type,
        parsed_result=parsed_result,
        source_text=source_text or (parsed_result.source_text if parsed_result else ""),
        error=parse_error if file_type == UNKNOWN else None,
    )


def _classify_from_name(file_name: str) -> str | None:
    label = _normalize(file_name)
    if re.search(r"\b(correlogram|correlation|acf)\b", label):
        return CORRELOGRAM
    if re.search(r"\b(summary|statistics|stats)\b", label):
        return SUMMARY_EXPORT
    if "intensity" in label and ("distribution" in label or "size" in label):
        return INTENSITY_DISTRIBUTION
    if "size distribution" in label:
        return INTENSITY_DISTRIBUTION
    return None


def _classify_from_parsed_result(result: ParsedDLSResult | None) -> str | None:
    if result is None:
        return None
    if result.metrics.get("Data Type") == "Measurement Summary":
        return SUMMARY_EXPORT
    if result.metrics.get("Intensity Column") and result.metrics.get("Diameter Column"):
        return INTENSITY_DISTRIBUTION
    return None


def _classify_from_text(text: str) -> str | None:
    label = _normalize(text[:4000])
    if "correlogram" in label or ("correlation" in label and ("delay" in label or "time" in label)):
        return CORRELOGRAM
    if ("z average" in label or "z avg" in label) and ("pdi" in label or "polydispers" in label):
        return SUMMARY_EXPORT
    if "intensity" in label and ("diameter" in label or "size nm" in label or "particle size" in label):
        return INTENSITY_DISTRIBUTION
    return None


def _safe_read_text(uploaded_file) -> str:
    try:
        return read_uploaded_text(uploaded_file)
    except (UnicodeDecodeError, ValueError):
        return ""


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
