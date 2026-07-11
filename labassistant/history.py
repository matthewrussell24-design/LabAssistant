from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from labassistant.models import (
    AngleSummary,
    DerivedMetrics,
    DistributionData,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    SummaryMetrics,
    ChromatogramTrace,
    ChromatographyMeasurement,
    ChromatographyPeak,
)
from labassistant.quality import status_from_warnings


DEFAULT_HISTORY_PATH = Path(".labassistant_history/experiments.jsonl")

# Drift thresholds for comparing a batch to a previous saved run.
Z_DRIFT_PERCENT = 20.0
PDI_DRIFT_ABSOLUTE = 0.10

# Feature weights for similar-run search. Size features contribute a log10 ratio
# (size is log-distributed) and PDI an absolute difference; both land on a
# comparable "meaningful change" scale (a 25% size shift ~= log10 0.097 ~= a PDI
# move of 0.1), so equal-ish weights are reasonable.
SIMILARITY_WEIGHTS = {"z_average": 1.0, "pdi": 1.0, "primary_peak": 0.8}


@dataclass
class ExperimentRecord:
    id: str
    saved_at: str
    label: str
    measurements: list[dict]

    @classmethod
    def from_measurements(cls, measurements: list[object], label: str = "") -> "ExperimentRecord":
        return cls(
            id=uuid4().hex,
            saved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            label=label.strip() or "Untitled experiment",
            measurements=[measurement.to_dict() for measurement in measurements],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "saved_at": self.saved_at,
            "label": self.label,
            "measurements": self.measurements,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ExperimentRecord":
        return cls(
            id=str(payload.get("id", "")),
            saved_at=str(payload.get("saved_at", "")),
            label=str(payload.get("label") or "Untitled experiment"),
            measurements=list(payload.get("measurements") or []),
        )


class ExperimentRecordNotFoundError(LookupError):
    """Raised when a requested history record does not exist."""


class MalformedExperimentRecordError(ValueError):
    """Raised when a requested history record cannot be reconstructed safely."""


def measurements_from_record(record: ExperimentRecord) -> list[Measurement]:
    measurements = []
    for payload in record.measurements:
        measurement = measurement_from_dict(payload)
        measurement.provenance.setdefault("loaded_from_history", {})
        measurement.provenance["loaded_from_history"] = {
            "record_id": record.id,
            "label": record.label,
            "saved_at": record.saved_at,
        }
        measurements.append(measurement)
    return measurements


def chromatography_measurements_from_record(
    record: ExperimentRecord,
) -> list[ChromatographyMeasurement]:
    """Reconstruct chromatography evidence with persisted-record provenance."""

    if not record.measurements:
        raise MalformedExperimentRecordError(
            f"Malformed experiment record {record.id}: no chromatography measurements"
        )
    measurements = []
    for payload in record.measurements:
        if not isinstance(payload, dict) or not isinstance(payload.get("sample_name"), str):
            raise MalformedExperimentRecordError(
                f"Malformed experiment record {record.id}: not a chromatography measurement"
            )
        try:
            measurement = chromatography_measurement_from_dict(payload)
        except (TypeError, ValueError) as error:
            raise MalformedExperimentRecordError(
                f"Malformed experiment record {record.id}: invalid chromatography payload"
            ) from error
        measurement.metadata = dict(measurement.metadata)
        measurement.metadata["loaded_from_history"] = {
            "record_id": record.id,
            "label": record.label,
            "saved_at": record.saved_at,
        }
        measurements.append(measurement)
    return measurements


def chromatography_measurement_from_dict(payload: dict) -> ChromatographyMeasurement:
    """Restore nested chromatography dataclasses while tolerating newer fields."""

    peaks_payload = payload.get("peaks") or []
    traces_payload = payload.get("chromatogram_traces") or []
    if not isinstance(peaks_payload, list) or not all(isinstance(item, dict) for item in peaks_payload):
        raise TypeError("peaks must be a list of objects")
    if not isinstance(traces_payload, list) or not all(isinstance(item, dict) for item in traces_payload):
        raise TypeError("chromatogram_traces must be a list of objects")
    values = {
        key: value
        for key, value in payload.items()
        if key in ChromatographyMeasurement.__dataclass_fields__
        and key not in {"peaks", "chromatogram_traces"}
    }
    values["peaks"] = [_dataclass_from_dict(ChromatographyPeak, item) for item in peaks_payload]
    values["chromatogram_traces"] = [
        _dataclass_from_dict(ChromatogramTrace, item) for item in traces_payload
    ]
    return ChromatographyMeasurement(**values)


def measurement_from_dict(payload: dict) -> Measurement:
    metadata = _dataclass_from_dict(MeasurementMetadata, payload.get("metadata") or {})
    summary_metrics = _dataclass_from_dict(SummaryMetrics, payload.get("summary_metrics") or {})
    derived_metrics = _dataclass_from_dict(DerivedMetrics, payload.get("derived_metrics") or {})
    distributions = {
        key: _dataclass_from_dict(DistributionData, value)
        for key, value in (payload.get("distributions") or {}).items()
        if isinstance(value, dict)
    }
    angle_summaries = [
        _dataclass_from_dict(AngleSummary, value)
        for value in payload.get("angle_summaries") or []
        if isinstance(value, dict)
    ]
    flags = [
        _dataclass_from_dict(MeasurementFlag, value)
        for value in payload.get("flags") or []
        if isinstance(value, dict)
    ]
    return Measurement(
        metadata=metadata,
        summary_metrics=summary_metrics,
        distributions=distributions,
        correlogram=list(payload.get("correlogram") or []),
        derived_metrics=derived_metrics,
        angle_summaries=angle_summaries,
        flags=flags,
        interpretation=dict(payload.get("interpretation") or {}),
        provenance=dict(payload.get("provenance") or {}),
    )


def _dataclass_from_dict(dataclass_type, payload: dict):
    names = set(dataclass_type.__dataclass_fields__)
    return dataclass_type(**{key: value for key, value in payload.items() if key in names})


def save_experiment(
    measurements: list[object],
    label: str = "",
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> ExperimentRecord:
    record = ExperimentRecord.from_measurements(measurements, label)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return record


def load_history(history_path: Path = DEFAULT_HISTORY_PATH) -> list[ExperimentRecord]:
    if not history_path.exists():
        return []

    records = []
    with history_path.open("r", encoding="utf-8") as history_file:
        for line in history_file:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(ExperimentRecord.from_dict(json.loads(line)))
            except json.JSONDecodeError:
                continue
    return records


def load_experiment_record(
    record_id: str,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> ExperimentRecord:
    """Load one valid history record by id with explicit lookup errors.

    Unlike the tolerant history browser, this targeted read fails if a JSONL
    line is malformed because silently stepping over damaged persistence would
    make a successful lookup ambiguous.
    """

    requested_id = record_id.strip()
    if not requested_id:
        raise ExperimentRecordNotFoundError("Experiment record id is required")
    if not history_path.exists():
        raise ExperimentRecordNotFoundError(f"Experiment record not found: {requested_id}")

    with history_path.open("r", encoding="utf-8") as history_file:
        for line_number, line in enumerate(history_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise MalformedExperimentRecordError(
                    f"Malformed experiment history at line {line_number}"
                ) from error
            if not isinstance(payload, dict):
                raise MalformedExperimentRecordError(
                    f"Malformed experiment history at line {line_number}: expected an object"
                )
            if str(payload.get("id", "")) != requested_id:
                continue
            measurements = payload.get("measurements")
            if not isinstance(measurements, list) or not all(
                isinstance(measurement, dict) for measurement in measurements
            ):
                raise MalformedExperimentRecordError(
                    f"Malformed experiment record {requested_id}: measurements must be a list of objects"
                )
            record = ExperimentRecord.from_dict(payload)
            try:
                if measurements and all("sample_name" in measurement for measurement in measurements):
                    chromatography_measurements_from_record(record)
                else:
                    measurements_from_record(record)
            except (AttributeError, TypeError, ValueError) as error:
                raise MalformedExperimentRecordError(
                    f"Malformed experiment record {requested_id}: invalid measurement payload"
                ) from error
            return record

    raise ExperimentRecordNotFoundError(f"Experiment record not found: {requested_id}")


def history_table(records: list[ExperimentRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        measurements = record.measurements
        pdi_values = [_metric_value(measurement, "summary_metrics", "pdi") for measurement in measurements]
        z_values = [_metric_value(measurement, "summary_metrics", "z_average") for measurement in measurements]
        statuses = [_status_from_measurement_dict(measurement) for measurement in measurements]
        rows.append(
            {
                "Saved At": record.saved_at,
                "Experiment": record.label,
                "Measurements": len(measurements),
                "Flagged": sum(status != "Normal" for status in statuses),
                "Review": sum(status == "Review" for status in statuses),
                "Median Z-Average": _median(z_values),
                "Median PDI": _median(pdi_values),
                "Record ID": record.id,
            }
        )
    return pd.DataFrame(rows)


def trend_table(records: list[ExperimentRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        for measurement in record.measurements:
            rows.append(
                {
                    "Saved At": record.saved_at,
                    "Experiment": record.label,
                    "Sample": measurement.get("metadata", {}).get("sample_name"),
                    "Z-Average": _metric_value(measurement, "summary_metrics", "z_average"),
                    "PDI": _metric_value(measurement, "summary_metrics", "pdi"),
                    "Status": _status_from_measurement_dict(measurement),
                }
            )
    return pd.DataFrame(rows)


def latest_experiment(records: list[ExperimentRecord], exclude_id: str | None = None) -> ExperimentRecord | None:
    """Most recently saved experiment, optionally skipping one record id.

    Records are appended chronologically, so ties on ``saved_at`` (which is only
    second-resolution) are broken by position: the last-appended record wins.
    """
    candidates = [record for record in records if record.id != exclude_id]
    if not candidates:
        return None
    return max(enumerate(candidates), key=lambda item: (item[1].saved_at, item[0]))[1]


def compare_experiments(
    current: list[Measurement],
    previous: ExperimentRecord | None,
    z_drift_percent: float = Z_DRIFT_PERCENT,
    pdi_drift_absolute: float = PDI_DRIFT_ABSOLUTE,
) -> pd.DataFrame:
    """Compare a current batch to a previous saved experiment by sample name.

    Returns one row per current sample with its Z-average and PDI, the previous
    values (when the sample name matches), the change, and a drift label. A
    sample with no prior match is "New sample"; matched samples are "Stable"
    unless the Z-average moves by at least ``z_drift_percent`` or the PDI moves
    by at least ``pdi_drift_absolute``.
    """
    previous_by_name = {}
    if previous is not None:
        for measurement in previous.measurements:
            entry = _sample_metrics_from_dict(measurement)
            if entry["name"]:
                previous_by_name[entry["name"]] = entry

    rows = []
    for measurement in current:
        entry = _sample_metrics_from_measurement(measurement)
        prior = previous_by_name.get(entry["name"])
        prior_z = prior["z_average"] if prior else None
        prior_pdi = prior["pdi"] if prior else None
        z_change = _percent_change(prior_z, entry["z_average"])
        pdi_change = _difference(prior_pdi, entry["pdi"])
        rows.append(
            {
                "Sample": entry["name"],
                "Z-Average": entry["z_average"],
                "Previous Z-Average": prior_z,
                "Z Change %": z_change,
                "PDI": entry["pdi"],
                "Previous PDI": prior_pdi,
                "PDI Change": pdi_change,
                "Drift": _drift_label(prior, z_change, pdi_change, z_drift_percent, pdi_drift_absolute),
            }
        )
    return pd.DataFrame(rows)


def compare_to_history(
    current: list[Measurement],
    history_path: Path = DEFAULT_HISTORY_PATH,
    exclude_id: str | None = None,
) -> pd.DataFrame:
    """Compare a current batch to the most recent saved experiment on disk."""
    return compare_experiments(current, latest_experiment(load_history(history_path), exclude_id=exclude_id))


def find_similar_samples(
    measurement: Measurement,
    records: list[ExperimentRecord],
    top_n: int = 5,
    exclude_id: str | None = None,
) -> pd.DataFrame:
    """Rank past saved samples by similarity to a query measurement.

    Distance is a unit-aware, weight-normalized blend: log10 ratio for size
    features (Z-average, primary peak) and absolute difference for PDI. Only
    features present on both sides contribute, and the distance is divided by the
    weight actually used so partially-populated records stay comparable. Lower
    distance is more similar; ``Similarity`` is a 0-100 readability score
    (``100 * exp(-3 * distance)``), not a probability.
    """
    query = _feature_vector_from_measurement(measurement)

    rows = []
    for record in records:
        if record.id == exclude_id:
            continue
        for stored in record.measurements:
            candidate = _feature_vector_from_dict(stored)
            distance = _feature_distance(query, candidate)
            if distance is None:
                continue
            rows.append(
                {
                    "Experiment": record.label,
                    "Saved At": record.saved_at,
                    "Sample": candidate["name"],
                    "Z-Average": candidate["z_average"],
                    "PDI": candidate["pdi"],
                    "Primary Peak": candidate["primary_peak"],
                    "Distance": round(distance, 4),
                    "Similarity": round(100.0 * math.exp(-3.0 * distance), 1),
                }
            )

    table = pd.DataFrame(rows, columns=["Experiment", "Saved At", "Sample", "Z-Average", "PDI", "Primary Peak", "Distance", "Similarity"])
    if table.empty:
        return table
    return table.sort_values(["Distance", "Saved At"]).head(top_n).reset_index(drop=True)


def _feature_vector_from_measurement(measurement: Measurement) -> dict:
    return {
        "name": measurement.metadata.sample_name,
        "z_average": measurement.summary_metrics.z_average,
        "pdi": measurement.summary_metrics.pdi,
        "primary_peak": measurement.derived_metrics.primary_peak_nm,
    }


def _feature_vector_from_dict(measurement: dict) -> dict:
    return {
        "name": measurement.get("metadata", {}).get("sample_name"),
        "z_average": _metric_value(measurement, "summary_metrics", "z_average"),
        "pdi": _metric_value(measurement, "summary_metrics", "pdi"),
        "primary_peak": _metric_value(measurement, "derived_metrics", "primary_peak_nm"),
    }


def _feature_distance(query: dict, candidate: dict) -> float | None:
    total = 0.0
    used_weight = 0.0

    for feature in ("z_average", "primary_peak"):
        contribution = _log_ratio_distance(query.get(feature), candidate.get(feature))
        if contribution is not None:
            total += SIMILARITY_WEIGHTS[feature] * contribution
            used_weight += SIMILARITY_WEIGHTS[feature]

    pdi_query = query.get("pdi")
    pdi_candidate = candidate.get("pdi")
    if pdi_query is not None and pdi_candidate is not None:
        total += SIMILARITY_WEIGHTS["pdi"] * abs(pdi_query - pdi_candidate)
        used_weight += SIMILARITY_WEIGHTS["pdi"]

    if used_weight == 0:
        return None
    return total / used_weight


def _log_ratio_distance(query_value: float | None, candidate_value: float | None) -> float | None:
    if query_value is None or candidate_value is None or query_value <= 0 or candidate_value <= 0:
        return None
    return abs(math.log10(query_value) - math.log10(candidate_value))


def _sample_metrics_from_measurement(measurement: Measurement) -> dict:
    return {
        "name": measurement.metadata.sample_name,
        "z_average": measurement.summary_metrics.z_average,
        "pdi": measurement.summary_metrics.pdi,
    }


def _sample_metrics_from_dict(measurement: dict) -> dict:
    return {
        "name": measurement.get("metadata", {}).get("sample_name"),
        "z_average": _metric_value(measurement, "summary_metrics", "z_average"),
        "pdi": _metric_value(measurement, "summary_metrics", "pdi"),
    }


def _percent_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0:
        return None
    return float((current - previous) / previous * 100.0)


def _difference(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None:
        return None
    return float(current - previous)


def _drift_label(
    prior: dict | None,
    z_change: float | None,
    pdi_change: float | None,
    z_drift_percent: float,
    pdi_drift_absolute: float,
) -> str:
    if prior is None:
        return "New sample"
    flags = []
    if z_change is not None and abs(z_change) >= z_drift_percent:
        flags.append("Z-average drift")
    if pdi_change is not None and abs(pdi_change) >= pdi_drift_absolute:
        flags.append("PDI drift")
    return ", ".join(flags) if flags else "Stable"


def _metric_value(measurement: dict, group: str, key: str) -> float | None:
    value = measurement.get(group, {}).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _median(values: list[float | None]) -> float | None:
    clean_values = pd.Series(values, dtype="float64").dropna()
    if clean_values.empty:
        return None
    return float(clean_values.median())


def _status_from_measurement_dict(measurement: dict) -> str:
    warnings = [flag.get("label", "") for flag in measurement.get("flags", [])]
    return status_from_warnings(warnings)
