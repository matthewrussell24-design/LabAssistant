from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import unquote
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

from labassistant.models import ChromatographyMeasurement, ChromatographyPeak, Experiment, Observation


TEXT_SUFFIXES = {
    ".xml",
    ".txt",
    ".csv",
    ".json",
    ".tsv",
    ".ini",
    ".aml",
    ".acaml",
    ".mfx",
    ".psmdcp",
}
NESTED_OPENLAB_SUFFIXES = {".rx", ".dx", ".sqx", ".amx"}
SIGNAL_HINTS = ("signal", "chrom", "chromatogram", "dad", "uv", "tic", "fid", "msd", ".ch", ".uv", ".dx")
PEAK_TABLE_HINTS = ("peak", "compound", "result", "integration", "amount")
SEQUENCE_HINTS = ("sequence", "sample", "injection", "method", "run", ".sqx", ".acaml", ".rx")

# Recognized Agilent/OpenLab detector signal containers. Extensions come from
# ChemStation/OpenLab CDS conventions; tokens catch detector-named files such as
# "DAD1A.CH" or "VWD1A". Anything that looks like a signal but matches neither is
# reported as an unknown detector file rather than silently ignored.
KNOWN_DETECTOR_EXTS = {".ch", ".uv", ".ms", ".dad", ".fid", ".tic", ".sd", ".ls", ".d", ".dx"}
KNOWN_DETECTOR_TOKENS = ("dad", "vwd", "mwd", "fld", "adc", "msd", "ms", "tcd", "fid", "uv", "ri")

# Method / processing / audit / calibration classification tokens.
ACQ_METHOD_HINTS = ("acqmethod", "acquisition", "acq.m", "amethod", ".m/", "instrumentmethod", ".amx")
PROCESSING_METHOD_HINTS = ("processing", "damethod", "procmethod", "dataanalysis", "reportlayout", ".rdl", ".pmd")
AUDIT_HINTS = ("audit", "signaturelog", "auditlog", "audittrail", ".rx")
CALIBRATION_HINTS = ("calibration", "calib", "cal_curve", "calcurve")


@dataclass
class OpenLabInjection:
    sample_name: str
    injection_order: int | None = None
    method: str | None = None
    measurement_datetime: str | None = None
    raw_data_file: str | None = None
    run_time_min: float | None = None
    source_file: str | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenLabOlaxImportResult:
    source_path: str
    is_zip: bool
    archive_entries: list[str] = field(default_factory=list)
    sequence_metadata: dict[str, Any] = field(default_factory=dict)
    injections: list[OpenLabInjection] = field(default_factory=list)
    signal_files: list[str] = field(default_factory=list)
    peak_table_files: list[str] = field(default_factory=list)
    detector_files: list[str] = field(default_factory=list)
    unknown_detector_files: list[str] = field(default_factory=list)
    acquisition_method_files: list[str] = field(default_factory=list)
    processing_method_files: list[str] = field(default_factory=list)
    audit_files: list[str] = field(default_factory=list)
    calibration_files: list[str] = field(default_factory=list)
    peaks_by_sample: dict[str, list[ChromatographyPeak]] = field(default_factory=dict)
    unassigned_peaks: list[ChromatographyPeak] = field(default_factory=list)
    measurements: list[ChromatographyMeasurement] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    readable_text_files: list[str] = field(default_factory=list)
    unsupported_sections: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def report_lines(self) -> list[str]:
        lines = [
            f"Source: {self.source_path}",
            f"Archive readable: {'yes' if self.is_zip else 'no'}",
            f"Archive entries: {len(self.archive_entries)}",
            f"Readable text metadata files: {len(self.readable_text_files)}",
            f"Sequence metadata keys: {', '.join(sorted(self.sequence_metadata)) or 'none'}",
            f"Injections found: {len(self.injections)}",
            f"Chromatogram signal files: {len(self.signal_files)}",
            f"Peak/result table files: {len(self.peak_table_files)}",
            f"Measurements created: {len(self.measurements)}",
            f"Observations generated: {len(self.observations)}",
        ]
        if self.injections:
            lines.append("Injection summary:")
            for injection in self.injections:
                lines.append(
                    "- "
                    + " | ".join(
                        [
                            f"order={injection.injection_order if injection.injection_order is not None else 'unknown'}",
                            f"sample={injection.sample_name}",
                            f"method={injection.method or 'unknown'}",
                            f"run_time={injection.run_time_min if injection.run_time_min is not None else 'unknown'}",
                            f"source={injection.source_file or 'unknown'}",
                        ]
                    )
                )
        if self.signal_files:
            lines.append("Signal files:")
            lines.extend(f"- {name}" for name in self.signal_files[:20])
        if self.peak_table_files:
            lines.append("Peak/result files:")
            lines.extend(f"- {name}" for name in self.peak_table_files[:20])
        else:
            lines.append("Peak/result files: none found; peak table decoding still needed.")
        if self.errors:
            lines.append("Parser notes/errors:")
            lines.extend(f"- {error}" for error in self.errors)
        return lines


def inspect_openlab_olax(path: str | Path) -> OpenLabOlaxImportResult:
    source = Path(path)
    result = OpenLabOlaxImportResult(source_path=str(source), is_zip=False)
    if not source.exists():
        result.errors.append("File does not exist.")
        return result

    if not zipfile.is_zipfile(source):
        result.errors.append("File is not a readable ZIP/Open Packaging archive.")
        return result

    result.is_zip = True
    try:
        with zipfile.ZipFile(source) as archive:
            result.archive_entries = sorted(info.filename for info in archive.infolist() if not info.is_dir())
            result.signal_files = _locate_signal_files(result.archive_entries)
            result.peak_table_files = _locate_peak_table_files(result.archive_entries)
            result.detector_files, result.unknown_detector_files = _classify_detector_files(result.signal_files)
            result.acquisition_method_files = _locate_by_hints(result.archive_entries, ACQ_METHOD_HINTS)
            result.processing_method_files = _locate_by_hints(result.archive_entries, PROCESSING_METHOD_HINTS)
            result.audit_files = _locate_by_hints(result.archive_entries, AUDIT_HINTS)
            result.calibration_files = _locate_by_hints(result.archive_entries, CALIBRATION_HINTS)

            text_payloads = _read_text_payloads(archive, result.archive_entries)
            result.readable_text_files = sorted(text_payloads)
            result.sequence_metadata = _extract_sequence_metadata(text_payloads)
            result.injections = _extract_injections(text_payloads, result.archive_entries)
            result.peaks_by_sample, result.unassigned_peaks = _extract_peak_tables(
                text_payloads,
                result.peak_table_files,
            )
    except (zipfile.BadZipFile, OSError) as error:
        result.errors.append(f"Archive could not be fully read: {error}")

    result.unsupported_sections = _detect_unsupported_sections(result)
    result.measurements = _measurements_from_injections(
        result.injections,
        result.signal_files,
        result.peak_table_files,
        result.peaks_by_sample,
        result.unassigned_peaks,
    )
    result.observations = _observations_from_result(result)
    return result


def build_experiment_from_olax(path: str | Path, *, label: str | None = None) -> Experiment:
    """Open an .olax archive and return a fully populated Experiment.

    This is the instrument adapter entry point: it enumerates injections,
    extracts metadata, locates signals/peak tables, builds
    ChromatographyMeasurement objects and attaches the Observation stream. The
    reasoning layer (Investigator, mass balance) works from the returned
    Experiment and never re-reads the archive.
    """
    result = inspect_openlab_olax(path)
    sequence_name = result.sequence_metadata.get("sequence_name") or result.sequence_metadata.get("sequence")
    experiment_label = label or (str(sequence_name) if sequence_name else Path(str(path)).stem)
    return Experiment(
        experiment_id=uuid4().hex,
        label=experiment_label,
        instrument="Agilent OpenLab CDS",
        technique="HPLC",
        source_path=str(path),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        measurements=list(result.measurements),
        observations=list(result.observations),
        unsupported_sections=list(result.unsupported_sections),
        metadata={
            "sequence_metadata": result.sequence_metadata,
            "archive_entry_count": len(result.archive_entries),
            "signal_files": result.signal_files,
            "peak_table_files": result.peak_table_files,
            "detector_files": result.detector_files,
            "unknown_detector_files": result.unknown_detector_files,
            "acquisition_method_files": result.acquisition_method_files,
            "processing_method_files": result.processing_method_files,
            "audit_files": result.audit_files,
            "calibration_files": result.calibration_files,
            "parsed_peak_count": sum(len(peaks) for peaks in result.peaks_by_sample.values())
            + len(result.unassigned_peaks),
            "injection_count": len(result.injections),
            "errors": result.errors,
        },
    )


def parser_report(path: str | Path) -> str:
    return "\n".join(inspect_openlab_olax(path).report_lines())


def _locate_signal_files(entries: list[str]) -> list[str]:
    return [
        entry
        for entry in entries
        if any(hint in _entry_name(entry).lower() for hint in SIGNAL_HINTS)
        and not any(hint in _entry_name(entry).lower() for hint in PEAK_TABLE_HINTS)
    ]


def _locate_peak_table_files(entries: list[str]) -> list[str]:
    return [entry for entry in entries if any(hint in _entry_name(entry).lower() for hint in PEAK_TABLE_HINTS)]


def _locate_by_hints(entries: list[str], hints: tuple[str, ...]) -> list[str]:
    return [entry for entry in entries if any(hint in _entry_name(entry).lower() for hint in hints)]


def _classify_detector_files(signal_files: list[str]) -> tuple[list[str], list[str]]:
    """Split candidate signal files into recognized detectors vs unknown.

    A file is a recognized detector artifact if its extension is a known
    OpenLab/ChemStation signal container or its name carries a detector token
    (DAD, VWD, MWD, FID, ...). Everything else that looked signal-like by the
    coarse hint scan is surfaced as an unknown detector file so nothing is
    dropped silently.
    """
    known: list[str] = []
    unknown: list[str] = []
    for entry in signal_files:
        lower = _entry_name(entry).lower()
        suffix = Path(entry).suffix.lower()
        name_tokens = re.split(r"[^a-z0-9]+", Path(lower).name)
        has_detector_token = any(
            token in name_tokens or token in lower for token in KNOWN_DETECTOR_TOKENS
        )
        if suffix in KNOWN_DETECTOR_EXTS or has_detector_token:
            known.append(entry)
        else:
            unknown.append(entry)
    return known, unknown


def _detect_unsupported_sections(result: "OpenLabOlaxImportResult") -> list[str]:
    """List archive sections present but not yet decoded, for honest reporting."""
    unsupported: list[str] = []
    if result.signal_files:
        unsupported.append(
            "Raw chromatogram signal traces are located but not decoded to time/intensity arrays "
            f"({len(result.signal_files)} file(s))."
        )
    if result.audit_files:
        unsupported.append(
            f"Audit trail present but not parsed ({len(result.audit_files)} file(s))."
        )
    if result.calibration_files:
        unsupported.append(
            f"Calibration data present but not parsed ({len(result.calibration_files)} file(s))."
        )
    return unsupported


def _read_text_payloads(archive: zipfile.ZipFile, entries: list[str]) -> dict[str, str]:
    payloads = {}
    for entry in entries:
        entry_name = _entry_name(entry)
        suffix = Path(entry_name).suffix.lower()
        if suffix in NESTED_OPENLAB_SUFFIXES:
            payloads.update(_read_nested_text_payloads(archive, entry))
            continue
        if suffix not in TEXT_SUFFIXES and not any(hint in entry_name.lower() for hint in SEQUENCE_HINTS):
            continue
        try:
            data = archive.read(entry)
        except (KeyError, RuntimeError, zipfile.BadZipFile):
            continue
        text = _decode_text_payload(data)
        if text.strip():
            payloads[entry_name] = text
    return payloads


def _read_nested_text_payloads(archive: zipfile.ZipFile, entry: str) -> dict[str, str]:
    payloads: dict[str, str] = {}
    try:
        data = archive.read(entry)
    except (KeyError, RuntimeError, zipfile.BadZipFile):
        return payloads
    nested = io.BytesIO(data)
    if not zipfile.is_zipfile(nested):
        return payloads
    nested.seek(0)
    try:
        with zipfile.ZipFile(nested) as nested_archive:
            for info in nested_archive.infolist():
                if info.is_dir():
                    continue
                name = _entry_name(info.filename)
                suffix = Path(name).suffix.lower()
                if suffix not in TEXT_SUFFIXES and not any(
                    hint in name.lower() for hint in ("sample", "injection", "sequence", "audit", "content_type")
                ):
                    continue
                try:
                    text = _decode_text_payload(nested_archive.read(info.filename))
                except (KeyError, RuntimeError, zipfile.BadZipFile):
                    continue
                if text.strip():
                    payloads[f"{_entry_name(entry)}::{name}"] = text
    except (zipfile.BadZipFile, OSError):
        return payloads
    return payloads


def _decode_text_payload(data: bytes) -> str:
    if b"\x00" in data[:2000]:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="ignore")


def _extract_sequence_metadata(payloads: dict[str, str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name, text in payloads.items():
        lower_name = name.lower()
        if "sequence" in lower_name or ".sqx" in lower_name:
            metadata.setdefault("sequence_files", []).append(name)
        if "method" in lower_name or ".amx" in lower_name:
            metadata.setdefault("method_files", []).append(name)

        if Path(name).suffix.lower() == ".json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    normalized = _normalize_key(key)
                    if normalized in {"sequence_name", "sequence", "method", "operator", "instrument"}:
                        metadata.setdefault(normalized, value)

        xml_fields = _flat_xml_fields(text)
        for key, value in xml_fields.items():
            normalized = _normalize_key(key)
            if normalized in {
                "sequence_name",
                "sequence",
                "method",
                "operator",
                "instrument",
                "sequence_description",
                "description",
                "created_by_user",
                "creation_date",
                "client_name",
                "title",
                "creator",
            }:
                metadata.setdefault(normalized, value)
    return metadata


def _extract_injections(payloads: dict[str, str], entries: list[str]) -> list[OpenLabInjection]:
    injections: list[OpenLabInjection] = []
    for name, text in payloads.items():
        lower_name = name.lower()
        if any(hint in name.lower() for hint in PEAK_TABLE_HINTS):
            continue
        if not any(hint in lower_name for hint in SEQUENCE_HINTS):
            continue
        suffix = Path(name.split("::", 1)[-1]).suffix.lower()
        if suffix in {".xml", ".aml", ".acaml"} or name.endswith("InjectionACAML"):
            injections.extend(_injections_from_xml(name, text))
        elif suffix in {".csv", ".tsv", ".txt"}:
            injections.extend(_injections_from_delimited_text(name, text))
        elif suffix == ".json":
            injections.extend(_injections_from_json(name, text))

    if not injections:
        injections = _injections_from_entry_names(entries)

    return _dedupe_injections(injections)


def _injections_from_xml(name: str, text: str) -> list[OpenLabInjection]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    injections = []
    for element in root.iter():
        tag_name = _strip_namespace(element.tag).lower()
        if "injection" not in tag_name and "sample" not in tag_name:
            continue
        fields = {**element.attrib}
        for child in element:
            tag = _strip_namespace(child.tag)
            value = (child.text or "").strip()
            if value:
                fields[tag] = value
        if tag_name.startswith("samplecontainer"):
            continue
        injection = _injection_from_fields(fields, source_file=name)
        if injection:
            injections.append(injection)
    return injections


def _injections_from_delimited_text(name: str, text: str) -> list[OpenLabInjection]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    headers = [header.strip() for header in lines[0].split(delimiter)]
    injections = []
    for line in lines[1:]:
        values = [value.strip() for value in line.split(delimiter)]
        if len(values) != len(headers):
            continue
        fields = dict(zip(headers, values))
        injection = _injection_from_fields(fields, source_file=name)
        if injection:
            injections.append(injection)
    return injections


def _injections_from_json(name: str, text: str) -> list[OpenLabInjection]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    candidates = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("injections", "samples", "sequence"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
    injections = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            injection = _injection_from_fields(candidate, source_file=name)
            if injection:
                injections.append(injection)
    return injections


def _injections_from_entry_names(entries: list[str]) -> list[OpenLabInjection]:
    injections = []
    for entry in entries:
        normalized_entry = _entry_name(entry)
        suffix = Path(normalized_entry).suffix.lower()
        if suffix not in {".rx", ".dx"}:
            continue
        order = _openlab_order_from_entry(normalized_entry)
        injections.append(
            OpenLabInjection(
                sample_name=f"Injection {order}" if order is not None else Path(normalized_entry).stem,
                injection_order=order,
                source_file=normalized_entry,
                raw_fields={"inferred_from_path": normalized_entry},
            )
        )
    return injections


def _injection_from_fields(fields: dict[str, Any], source_file: str) -> OpenLabInjection | None:
    normalized = {_normalize_key(key): value for key, value in fields.items()}
    sample_name = _first_value(
        normalized,
        "sample_name",
        "sample",
        "sampleid",
        "sample_id",
        "sample_description",
        "sample_label",
        "name",
        "vial_name",
    )
    injection_id = _first_value(normalized, "injection_id", "injectionid")
    raw_data_file = _string_or_none(_first_value(normalized, "raw_data_file_name", "rawdatafilename", "raw_data_file"))
    if not sample_name:
        sample_name = _first_value(normalized, "sample_name", "samplename", "sample_id", "sampleid")
    if not sample_name and injection_id:
        sample_name = f"Injection {injection_id}"
    if not sample_name and "injection_metadata" in normalized:
        sample_name = str(normalized["injection_metadata"])
    if not sample_name:
        return None
    return OpenLabInjection(
        sample_name=str(sample_name),
        injection_order=_to_int(
            _first_value(
                normalized,
                "injection_order",
                "injection_number",
                "order",
                "run_order",
                "order_no",
            )
        )
        or (_openlab_order_from_entry(raw_data_file) if raw_data_file else None)
        or _to_int(
            _first_value(
                normalized,
                "injection_order",
                "injection",
                "injection_number",
                "order",
                "run_order",
                "order_no",
                "injection_id",
                "injectionid",
            )
        ),
        method=_string_or_none(
            _first_value(
                normalized,
                "method",
                "method_name",
                "acq_method",
                "acquisition_method",
                "acq_method_name",
                "acqmethodname",
            )
        ),
        measurement_datetime=_string_or_none(
            _first_value(normalized, "injection_acq_date_time", "injectionacqdatetime", "measurement_datetime")
        ),
        raw_data_file=raw_data_file,
        run_time_min=_to_float(_first_value(normalized, "run_time", "runtime", "run_time_min", "stop_time", "acq_time")),
        source_file=source_file,
        raw_fields={str(key): value for key, value in fields.items()},
    )


def _measurements_from_injections(
    injections: list[OpenLabInjection],
    signal_files: list[str],
    peak_table_files: list[str],
    peaks_by_sample: dict[str, list[ChromatographyPeak]] | None = None,
    unassigned_peaks: list[ChromatographyPeak] | None = None,
) -> list[ChromatographyMeasurement]:
    measurements = []
    peaks_by_sample = peaks_by_sample or {}
    unassigned_peaks = unassigned_peaks or []
    for injection in injections:
        injection_signal_files = _signal_files_for_injection(injection, signal_files)
        peaks = _peaks_for_injection(injection, peaks_by_sample, unassigned_peaks, len(injections))
        source_files = _unique(
            ([injection.source_file] if injection.source_file else [])
            + injection_signal_files
            + peak_table_files
        )
        measurements.append(
            ChromatographyMeasurement(
                sample_name=injection.sample_name,
                technique="HPLC",
                method_name=injection.method,
                injection_id=str(injection.injection_order) if injection.injection_order is not None else injection.sample_name,
                source_files=source_files,
                peaks=peaks,
                total_area=_sum_peak_area(peaks),
                notes=[
                    f"Signal files associated: {len(injection_signal_files)}",
                    f"Peak/result files detected: {len(peak_table_files)}",
                    f"Peaks parsed: {len(peaks)}",
                ],
                metadata={
                    "measurement_datetime": injection.measurement_datetime,
                    "run_time_min": injection.run_time_min,
                    "raw_data_file": injection.raw_data_file,
                    "raw_fields": injection.raw_fields,
                    "openlab_signal_files": injection_signal_files,
                    "openlab_all_signal_files": signal_files,
                    "openlab_peak_table_files": peak_table_files,
                },
            )
        )
    return measurements


def _extract_peak_tables(
    payloads: dict[str, str],
    peak_table_files: list[str],
) -> tuple[dict[str, list[ChromatographyPeak]], list[ChromatographyPeak]]:
    peaks_by_sample: dict[str, list[ChromatographyPeak]] = {}
    unassigned: list[ChromatographyPeak] = []
    for name in peak_table_files:
        text = payloads.get(name)
        if not text:
            continue
        for peak, sample_name in _peaks_from_delimited_table(name, text):
            if sample_name:
                peaks_by_sample.setdefault(_sample_key(sample_name), []).append(peak)
            else:
                unassigned.append(peak)
    return peaks_by_sample, unassigned


def _peaks_from_delimited_table(name: str, text: str) -> list[tuple[ChromatographyPeak, str | None]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    try:
        rows = list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter))
    except csv.Error:
        return []

    peaks: list[tuple[ChromatographyPeak, str | None]] = []
    for index, row in enumerate(rows, start=1):
        normalized = {_normalize_key(key): value for key, value in row.items() if key is not None}
        sample_name = _string_or_none(
            _first_value(normalized, "sample_name", "sample", "sampleid", "sample_id")
        )
        peak_name = _string_or_none(
            _first_value(normalized, "peak_name", "compound", "compound_name", "component", "component_name", "analyte")
        )
        peak_id = _string_or_none(_first_value(normalized, "peak_id", "peak", "peak_number", "id"))
        if not peak_id:
            peak_id = f"{Path(name).stem}:{index}"
        if not peak_name and peak_id and not str(peak_id).isdigit():
            peak_name = str(peak_id)
        peak = ChromatographyPeak(
            peak_id=str(peak_id),
            name=peak_name,
            role=_infer_peak_role(peak_name or str(peak_id)),
            retention_time_min=_to_float(
                _first_value(normalized, "retention_time", "retention_time_min", "rt", "rt_min", "time")
            ),
            area=_to_float(_first_value(normalized, "area", "peak_area", "area_counts")),
            area_percent=_to_float(_first_value(normalized, "area_percent", "area_pct", "percent_area", "area_")),
            height=_to_float(_first_value(normalized, "height", "peak_height")),
            width_seconds=_to_float(_first_value(normalized, "width", "width_seconds", "peak_width")),
            tailing_factor=_to_float(_first_value(normalized, "tailing", "tailing_factor", "tail_factor")),
            resolution=_to_float(_first_value(normalized, "resolution", "usp_resolution")),
            signal_to_noise=_to_float(_first_value(normalized, "signal_to_noise", "s_n", "sn")),
            integration_start_min=_to_float(_first_value(normalized, "start", "start_time", "integration_start")),
            integration_end_min=_to_float(_first_value(normalized, "end", "end_time", "integration_end")),
            metadata={"source_file": name, "raw_fields": {str(key): value for key, value in row.items()}},
        )
        peaks.append((peak, sample_name))
    return peaks


def _signal_files_for_injection(injection: OpenLabInjection, signal_files: list[str]) -> list[str]:
    if not signal_files:
        return []

    matches: list[str] = []
    sample_key = _sample_key(injection.sample_name)
    order = injection.injection_order
    order_patterns = []
    if order is not None:
        order_patterns = [
            rf"(^|[^0-9]){order}([^0-9]|$)",
            rf"(^|[^0-9]){order:02d}([^0-9]|$)",
            rf"(^|[^0-9]){order:03d}([^0-9]|$)",
        ]

    for signal_file in signal_files:
        lower = _entry_name(signal_file).lower()
        normalized_path = _sample_key(signal_file)
        order_match = bool(order_patterns and any(re.search(pattern, lower) for pattern in order_patterns))
        sample_match = bool(sample_key and sample_key in normalized_path)
        if order_match or sample_match:
            matches.append(signal_file)

    if matches:
        return matches
    if len(signal_files) == 1:
        return list(signal_files)
    return []


def _peaks_for_injection(
    injection: OpenLabInjection,
    peaks_by_sample: dict[str, list[ChromatographyPeak]],
    unassigned_peaks: list[ChromatographyPeak],
    injection_count: int,
) -> list[ChromatographyPeak]:
    sample_key = _sample_key(injection.sample_name)
    peaks = list(peaks_by_sample.get(sample_key, []))
    if not peaks and injection_count == 1:
        peaks.extend(unassigned_peaks)
    return peaks


def _sum_peak_area(peaks: list[ChromatographyPeak]) -> float | None:
    areas = [peak.area for peak in peaks if peak.area is not None]
    return sum(areas) if areas else None


def _infer_peak_role(label: str) -> str:
    normalized = _sample_key(label)
    if "parent" in normalized or "main" in normalized or "api" in normalized:
        return "parent"
    if "standard" in normalized or normalized.startswith("std"):
        return "standard"
    if "unknown" in normalized or "unk" in normalized:
        return "unknown"
    if "impurity" in normalized or "degradant" in normalized:
        return "known_impurity"
    return "unknown"


def _sample_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _entry_name(entry: str) -> str:
    """Normalize OpenLab package paths.

    Real `.olax` archives URL-encode Windows separators inside the ZIP name
    (`.rslt%5cfile.rx`). Normalizing early lets suffix checks and path matching
    work the same way for synthetic POSIX fixtures and real OpenLab exports.
    """
    return unquote(entry).replace("\\", "/")


def _openlab_order_from_entry(entry: str) -> int | None:
    stem = Path(entry).stem
    match = re.search(r"(?:^|[-_])(\d{1,3})$", stem)
    if match:
        return int(match.group(1))
    return _first_int(stem)


def _import_observation(
    result: "OpenLabOlaxImportResult",
    *,
    label: str,
    evidence: str,
    category: str = "chromatography_import",
    severity: str = "normal",
    confidence: str = "medium",
    recommendation: str | None = None,
) -> Observation:
    return Observation(
        label=label,
        category=category,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        source_type="openlab_olax",
        source_id=result.source_path,
        recommendation=recommendation,
    )


def _observations_from_result(result: OpenLabOlaxImportResult) -> list[Observation]:
    """Turn every archive discovery into structured Observations (Part 4).

    Positive facts use category ``chromatography_import``; anything missing that
    would limit interpretation uses category ``data_completeness`` so the
    Scientific Investigator can reason over gaps without re-reading the archive.
    """
    observations = [
        _import_observation(
            result,
            label="OpenLab sequence loaded",
            severity="normal" if result.is_zip else "review",
            confidence="high",
            evidence=f"Archive contains {len(result.archive_entries)} entries.",
        )
    ]

    if result.injections:
        observations.append(
            _import_observation(
                result,
                label="Injections found",
                evidence=f"Sequence contains {len(result.injections)} injection(s).",
            )
        )
        sample_types = _sample_type_counts(result.injections)
        if sample_types:
            observations.append(
                _import_observation(
                    result,
                    label="Blanks/standards/samples identified",
                    confidence="low",
                    evidence=", ".join(f"{key}: {value}" for key, value in sample_types.items()),
                )
            )
        label_by_kind = {
            "blank": "Blank injections detected",
            "standard": "Standards detected",
            "sample": "Sample injections detected",
        }
        for kind, obs_label in label_by_kind.items():
            count = sample_types.get(kind, 0)
            if count:
                observations.append(
                    _import_observation(
                        result,
                        label=obs_label,
                        confidence="low",
                        evidence=f"{count} {kind} injection(s) identified by sample-name heuristics.",
                    )
                )
    else:
        observations.append(
            _import_observation(
                result,
                label="No injections found",
                category="data_completeness",
                severity="review",
                evidence="No injections could be parsed from sequence metadata or archive layout.",
                recommendation="Confirm the archive is an OpenLab sequence export and re-run the importer.",
            )
        )

    if result.detector_files:
        observations.append(
            _import_observation(
                result,
                label="Chromatogram signal available",
                evidence=f"{len(result.detector_files)} recognized detector signal file(s) located.",
            )
        )

    if result.unknown_detector_files:
        observations.append(
            _import_observation(
                result,
                label="Unknown detector file",
                category="data_completeness",
                severity="watch",
                evidence=(
                    f"{len(result.unknown_detector_files)} signal-like file(s) had an unrecognized "
                    f"detector type: {', '.join(result.unknown_detector_files[:5])}."
                ),
                recommendation="Map the detector container format before decoding these traces.",
            )
        )

    if result.peak_table_files:
        observations.append(
            _import_observation(
                result,
                label="Peak table available",
                evidence=f"{len(result.peak_table_files)} result/peak table file(s) located.",
            )
        )
    else:
        observations.append(
            _import_observation(
                result,
                label="Missing peak table",
                category="data_completeness",
                severity="watch",
                evidence="No result/peak table file was detected by filename heuristics.",
                recommendation="Decode OpenLab result storage or export a peak table for quantitative analysis.",
            )
        )

    if result.acquisition_method_files:
        observations.append(
            _import_observation(
                result,
                label="Acquisition method available",
                evidence=f"{len(result.acquisition_method_files)} acquisition method file(s) located.",
            )
        )

    if not result.processing_method_files:
        observations.append(
            _import_observation(
                result,
                label="Processing method missing",
                category="data_completeness",
                severity="watch",
                evidence="No data-analysis/processing method file was detected.",
                recommendation="Attach the processing method to reproduce integration and quantitation.",
            )
        )

    if result.audit_files:
        observations.append(
            _import_observation(
                result,
                label="Audit trail available",
                evidence=f"{len(result.audit_files)} audit/signature file(s) located (not yet parsed).",
            )
        )

    if result.calibration_files:
        observations.append(
            _import_observation(
                result,
                label="Calibration data available",
                evidence=f"{len(result.calibration_files)} calibration file(s) located (not yet parsed).",
            )
        )

    return observations


def _sample_type_counts(injections: list[OpenLabInjection]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for injection in injections:
        name = injection.sample_name.lower()
        if "blank" in name:
            kind = "blank"
        elif "std" in name or "standard" in name:
            kind = "standard"
        else:
            kind = "sample"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _flat_xml_fields(text: str) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return {}
    fields = {}
    for element in root.iter():
        tag = _strip_namespace(element.tag)
        value = (element.text or "").strip()
        if value and len(value) < 500:
            fields[tag] = value
    return fields


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_key(key: Any) -> str:
    text = str(key).strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _first_value(fields: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = fields.get(key)
        if value not in (None, ""):
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return _first_int(str(value))


def _first_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _dedupe_injections(injections: list[OpenLabInjection]) -> list[OpenLabInjection]:
    deduped = []
    seen = set()
    for injection in injections:
        key = (injection.sample_name, injection.injection_order, injection.method)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(injection)
    return deduped
