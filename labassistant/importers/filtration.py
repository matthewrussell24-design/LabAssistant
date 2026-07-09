from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd

from labassistant.filtration import normalize_pressure, normalize_pressure_unit, validate_difficulty_score
from labassistant.models import FiltrationMeasurement


COLUMN_ALIASES = {
    "sample_name": {"sample", "sample name", "sample_name", "sample id", "sample_id"},
    "difficulty_score": {"difficulty score", "difficulty_score", "score", "filtration difficulty", "filtration_difficulty"},
    "filtration_time": {"filtration time", "filtration_time", "time", "time value"},
    "filtration_time_unit": {"filtration time unit", "filtration_time_unit", "time unit", "time_unit"},
    "pressure": {"pressure", "pressure value", "pressure_value"},
    "pressure_unit": {"pressure unit", "pressure_unit"},
    "filter_type": {"filter type", "filter_type", "filter", "membrane"},
    "clogging_observed": {"clogging observed", "clogging_observed", "clogging", "clogged"},
    "notes": {"notes", "note", "comments", "comment"},
}

TIME_UNITS_TO_MINUTES = {
    "seconds": 1 / 60,
    "second": 1 / 60,
    "sec": 1 / 60,
    "s": 1 / 60,
    "minutes": 1.0,
    "minute": 1.0,
    "min": 1.0,
    "m": 1.0,
    "hours": 60.0,
    "hour": 60.0,
    "hr": 60.0,
    "h": 60.0,
}


@dataclass
class FiltrationImportResult:
    measurements: list[FiltrationMeasurement] = field(default_factory=list)
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    unsupported_columns: list[str] = field(default_factory=list)
    source_name: str | None = None


def parse_filtration_csv(source: str | Path | TextIO | BinaryIO, source_name: str | None = None) -> FiltrationImportResult:
    table = pd.read_csv(source)
    column_map = _build_column_map(table.columns)
    missing = [column for column in ["sample_name", "difficulty_score"] if column not in column_map]
    unsupported = [str(column) for column in table.columns if column not in column_map.values()]
    result = FiltrationImportResult(
        table=table,
        missing_columns=missing,
        unsupported_columns=unsupported,
        source_name=source_name,
    )
    if missing:
        result.errors.append("Filtration CSV is missing required columns: " + ", ".join(missing))
        return result

    for row_index, row in table.iterrows():
        measurement, warnings = _measurement_from_row(row, column_map, row_index=row_index, source_name=source_name)
        result.warnings.extend(warnings)
        if measurement is not None:
            result.measurements.append(measurement)
    return result


def _build_column_map(columns) -> dict[str, str]:
    normalized_to_original = {_normalize_label(column): column for column in columns}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        matches = [normalized_to_original[alias] for alias in aliases if alias in normalized_to_original]
        if len(matches) == 1:
            mapping[canonical] = matches[0]
    return mapping


def _measurement_from_row(row: pd.Series, column_map: dict[str, str], *, row_index: int, source_name: str | None) -> tuple[FiltrationMeasurement | None, list[str]]:
    warnings: list[str] = []
    row_label = f"row {row_index + 2}"
    sample_name = _string_value(row, column_map.get("sample_name"))
    if not sample_name:
        return None, [f"{row_label}: missing sample name."]

    difficulty_score = validate_difficulty_score(_value(row, column_map.get("difficulty_score")))
    if difficulty_score is None:
        return None, [f"{row_label} ({sample_name}): difficulty score must be an integer from 1 to 5."]

    filtration_time_minutes = _filtration_time_minutes(row, column_map, row_label, warnings)
    pressure_value = _float_value(row, column_map.get("pressure"))
    pressure_unit = _string_value(row, column_map.get("pressure_unit"))
    pressure_kpa = None
    normalized_pressure_unit = normalize_pressure_unit(pressure_unit)
    if pressure_value is not None:
        if normalized_pressure_unit is None:
            warnings.append(f"{row_label} ({sample_name}): pressure value supplied without a supported pressure unit.")
        else:
            pressure_kpa = normalize_pressure(pressure_value, normalized_pressure_unit)
    elif pressure_unit:
        warnings.append(f"{row_label} ({sample_name}): pressure unit supplied without a pressure value.")

    return (
        FiltrationMeasurement(
            sample_name=sample_name,
            difficulty_score=float(difficulty_score),
            filtration_time_minutes=filtration_time_minutes,
            pressure=pressure_value,
            pressure_unit=normalized_pressure_unit,
            pressure_kpa=pressure_kpa,
            filter_type=_string_value(row, column_map.get("filter_type")),
            clogging_observed=_bool_value(row, column_map.get("clogging_observed")),
            notes=_string_value(row, column_map.get("notes")),
            source="csv_import",
            source_file=source_name,
            warnings=warnings,
            metadata={"row_number": row_index + 2, "pressure_unit_original": pressure_unit},
        ),
        warnings,
    )


def _filtration_time_minutes(row: pd.Series, column_map: dict[str, str], row_label: str, warnings: list[str]) -> float | None:
    value = _float_value(row, column_map.get("filtration_time"))
    unit = _string_value(row, column_map.get("filtration_time_unit"))
    if value is None:
        return None
    if not unit:
        warnings.append(f"{row_label}: filtration time supplied without a unit.")
        return None
    normalized_unit = unit.strip().lower()
    factor = TIME_UNITS_TO_MINUTES.get(normalized_unit)
    if factor is None:
        warnings.append(f"{row_label}: unsupported filtration time unit '{unit}'.")
        return None
    return value * factor


def _normalize_label(value) -> str:
    return str(value).strip().lower().replace("-", " ").replace("_", " ")


def _value(row: pd.Series, column: str | None):
    if not column:
        return None
    value = row.get(column)
    if value is None or pd.isna(value):
        return None
    return value


def _string_value(row: pd.Series, column: str | None) -> str | None:
    value = _value(row, column)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_value(row: pd.Series, column: str | None) -> float | None:
    value = _value(row, column)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_value(row: pd.Series, column: str | None) -> bool | None:
    value = _string_value(row, column)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"yes", "y", "true", "1", "observed"}:
        return True
    if normalized in {"no", "n", "false", "0", "none", "not observed"}:
        return False
    return None
