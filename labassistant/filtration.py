from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from labassistant.models import Observation


FILTRATION_DIFFICULTY_RUBRIC = {
    1: "Filters easily; no meaningful resistance.",
    2: "Slight resistance or slower than baseline.",
    3: "Moderate filtration difficulty.",
    4: "High resistance, substantial slowdown, or strong clogging tendency.",
    5: "Severe filtration difficulty; near-failure or inability to complete normally.",
}

PRESSURE_UNITS_TO_KPA = {
    "pa": 0.001,
    "kpa": 1.0,
    "bar": 100.0,
    "psi": 6.894757293168,
}

PRESSURE_UNIT_LABELS = {
    "pa": "Pa",
    "kpa": "kPa",
    "bar": "bar",
    "psi": "psi",
}


@dataclass
class FiltrationTrace:
    """Generic filtration-device trace without device-specific assumptions."""

    time_values: list[float] = field(default_factory=list)
    time_unit: str | None = None
    time_minutes: list[float] = field(default_factory=list)
    pressure_values: list[float] = field(default_factory=list)
    pressure_unit: str | None = None
    pressure_kpa: list[float] = field(default_factory=list)
    flow_rate_values: list[float] = field(default_factory=list)
    flow_rate_unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FiltrationMeasurement:
    """Orthogonal filtration evidence for one sample."""

    sample_name: str
    technique: str = "Filtration"
    difficulty_score: float | None = None
    filtration_time_minutes: float | None = None
    pressure: float | None = None
    pressure_unit: str | None = None
    pressure_kpa: float | None = None
    filter_type: str | None = None
    clogging_observed: bool | None = None
    notes: str | None = None
    source: str = "manual_entry"
    source_file: str | None = None
    warnings: list[str] = field(default_factory=list)
    trace: FiltrationTrace | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def observations_from_filtration_measurement(
    measurement: FiltrationMeasurement,
) -> list[Observation]:
    """Normalize filtration outcomes for instrument-independent reasoning."""

    from labassistant.models import Observation

    observations: list[Observation] = []
    source_id = measurement.source_file or measurement.source or measurement.sample_name
    difficulty = measurement.difficulty_score
    if difficulty is not None and difficulty >= 3:
        severity = "review" if difficulty >= 4 else "watch"
        observations.append(
            Observation(
                label="Filtration difficulty elevated",
                category="filtration_performance",
                sample_name=measurement.sample_name,
                severity=severity,
                confidence="high",
                evidence=f"Filtration difficulty score {difficulty:g}/5.",
                source_type="filtration_follow_up",
                source_id=source_id,
                recommendation="Inspect retained material and compare filtration behavior with particle and recovery evidence.",
            )
        )
    if measurement.clogging_observed is True:
        observations.append(
            Observation(
                label="Filter clogging observed",
                category="filtration_performance",
                sample_name=measurement.sample_name,
                severity="review",
                confidence="high",
                evidence="Clogging was recorded during filtration.",
                source_type="filtration_follow_up",
                source_id=source_id,
                recommendation="Characterize retained material before attributing the outcome to aggregation.",
            )
        )
    return observations


def normalize_pressure(value: float | int, unit: str) -> float:
    normalized_unit = normalize_pressure_unit(unit)
    if normalized_unit is None:
        raise ValueError(f"Unsupported pressure unit: {unit}")
    return float(value) * PRESSURE_UNITS_TO_KPA[normalized_unit]


def normalize_pressure_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = str(unit).strip().lower()
    if normalized in PRESSURE_UNITS_TO_KPA:
        return normalized
    return None


def pressure_unit_label(unit: str | None) -> str | None:
    normalized = normalize_pressure_unit(unit)
    if normalized is None:
        return None
    return PRESSURE_UNIT_LABELS[normalized]


def validate_difficulty_score(value: float | int | str | None) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not numeric.is_integer():
        return None
    score = int(numeric)
    return score if score in FILTRATION_DIFFICULTY_RUBRIC else None


def filtration_measurement_to_table_row(measurement: FiltrationMeasurement) -> dict[str, Any]:
    return {
        "Sample": measurement.sample_name,
        "Difficulty Score": measurement.difficulty_score,
        "Difficulty Meaning": FILTRATION_DIFFICULTY_RUBRIC.get(int(measurement.difficulty_score or 0), ""),
        "Filtration Time (min)": measurement.filtration_time_minutes,
        "Pressure": measurement.pressure,
        "Pressure Unit": pressure_unit_label(measurement.pressure_unit) or measurement.pressure_unit,
        "Pressure (kPa)": measurement.pressure_kpa,
        "Filter Type": measurement.filter_type,
        "Clogging": measurement.clogging_observed,
        "Source": measurement.source_file or measurement.source,
        "Notes": measurement.notes,
    }


def filtration_measurement_from_dict(payload: dict[str, Any], sample_name: str | None = None) -> FiltrationMeasurement:
    trace_payload = payload.get("trace")
    trace = _dataclass_from_dict(FiltrationTrace, trace_payload) if isinstance(trace_payload, dict) else None
    return FiltrationMeasurement(
        sample_name=str(payload.get("sample_name") or sample_name or ""),
        technique=str(payload.get("technique") or "Filtration"),
        difficulty_score=_optional_float(payload.get("difficulty_score")),
        filtration_time_minutes=_optional_float(payload.get("filtration_time_minutes")),
        pressure=_optional_float(payload.get("pressure")),
        pressure_unit=payload.get("pressure_unit"),
        pressure_kpa=_optional_float(payload.get("pressure_kpa")),
        filter_type=payload.get("filter_type"),
        clogging_observed=payload.get("clogging_observed"),
        notes=payload.get("notes"),
        source=str(payload.get("source") or "manual_entry"),
        source_file=payload.get("source_file"),
        warnings=list(payload.get("warnings") or []),
        trace=trace,
        metadata=dict(payload.get("metadata") or {}),
    )


def _dataclass_from_dict(dataclass_type, payload: dict[str, Any]):
    if not is_dataclass(dataclass_type):
        raise TypeError("dataclass_type must be a dataclass")
    names = {field.name for field in fields(dataclass_type)}
    return dataclass_type(**{key: value for key, value in payload.items() if key in names})


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
