from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd

from labassistant.chromatography import (
    observations_from_chromatography_measurement,
    observations_from_mass_balance_assessment,
)
from labassistant.models import ChromatographyMeasurement, ChromatographyPeak, MassBalanceAssessment, Observation


REQUIRED_COLUMNS = {
    "sample_id",
    "injection_number",
    "peak_name",
    "retention_time_min",
    "area",
    "height",
    "width",
    "tailing_factor",
    "known_or_unknown",
}
PARENT_NAMES = {"parent", "parent compound", "main", "main peak"}


def parse_chromatography_csv(source: str | Path | TextIO | BinaryIO) -> list[ChromatographyMeasurement]:
    table = pd.read_csv(source)
    missing = REQUIRED_COLUMNS - set(table.columns)
    if missing:
        raise ValueError(f"Chromatography CSV is missing required columns: {', '.join(sorted(missing))}")

    if "timepoint" not in table.columns:
        table["timepoint"] = table["injection_number"].astype(str)

    measurements: list[ChromatographyMeasurement] = []
    group_columns = ["sample_id", "timepoint", "injection_number"]
    for (sample_id, timepoint, injection_number), group in table.groupby(group_columns, sort=False):
        total_area = float(pd.to_numeric(group["area"], errors="coerce").fillna(0).sum())
        peaks = [_peak_from_row(row, total_area) for _, row in group.iterrows()]
        measurements.append(
            ChromatographyMeasurement(
                sample_name=str(sample_id),
                technique="HPLC",
                injection_id=f"{sample_id}-{timepoint}-inj{injection_number}",
                timepoint=str(timepoint),
                replicate_id=str(injection_number),
                peaks=peaks,
                total_area=total_area,
                parent_peak_id=next((peak.peak_id for peak in peaks if peak.role == "parent"), None),
            )
        )
    return measurements


def assess_chromatography_mass_balance(measurements: list[ChromatographyMeasurement]) -> MassBalanceAssessment:
    if not measurements:
        raise ValueError("At least one chromatography measurement is required.")

    timepoint_rows = _timepoint_summary(measurements)
    first = timepoint_rows[0]
    last = timepoint_rows[-1]
    sample_name = measurements[0].sample_name

    parent_change = _percent_change(last["parent_area"], first["parent_area"])
    known_change = _difference(last["known_impurity_area_percent"], first["known_impurity_area_percent"])
    total_change = _percent_change(last["total_area"], first["total_area"])
    missing_change = None if total_change is None else -total_change
    retention_shift = None
    if first["parent_retention_time_min"] is not None and last["parent_retention_time_min"] is not None:
        retention_shift = last["parent_retention_time_min"] - first["parent_retention_time_min"]

    replicate_rsd = _latest_total_area_rsd(measurements, last["timepoint"])
    assessment = MassBalanceAssessment(
        sample_name=sample_name,
        parent_change_percent=parent_change,
        parent_area_percent=last["parent_area_percent"],
        total_area_change_percent=total_change,
        known_impurity_change_percent=known_change,
        known_impurity_area_percent=last["known_impurity_area_percent"],
        unknown_area_percent=last["unknown_area_percent"],
        missing_area_change_percent=missing_change,
        retention_time_shift_min=retention_shift,
        replicate_rsd_percent=replicate_rsd,
        total_area_conserved=abs(total_change or 0.0) < 5.0,
        evidence={"timepoint_summary": timepoint_rows},
    )
    assessment.observations = observations_from_mass_balance_assessment(assessment)
    assessment.hypotheses = []
    return assessment


def chromatography_observations(measurements: list[ChromatographyMeasurement], assessment: MassBalanceAssessment) -> list[Observation]:
    observations: list[Observation] = []
    for measurement in measurements:
        observations.extend(observations_from_chromatography_measurement(measurement))
    observations.extend(assessment.observations)
    return _dedupe_observations(observations)


def peak_area_trend_table(measurements: list[ChromatographyMeasurement]) -> pd.DataFrame:
    rows = []
    for summary in _timepoint_summary(measurements):
        rows.append(
            {
                "Timepoint": summary["timepoint"],
                "Parent Area %": summary["parent_area_percent"],
                "Known Impurity Area %": summary["known_impurity_area_percent"],
                "Unknown Area %": summary["unknown_area_percent"],
                "Total Area": summary["total_area"],
                "Parent RT (min)": summary["parent_retention_time_min"],
            }
        )
    return pd.DataFrame(rows)


def total_area_trend_table(measurements: list[ChromatographyMeasurement]) -> pd.DataFrame:
    summary = _timepoint_summary(measurements)
    initial = summary[0]["total_area"] if summary else None
    rows = []
    for row in summary:
        rows.append(
            {
                "Timepoint": row["timepoint"],
                "Total Area": row["total_area"],
                "Change vs Start %": _percent_change(row["total_area"], initial),
            }
        )
    return pd.DataFrame(rows)


def _peak_from_row(row: pd.Series, total_area: float) -> ChromatographyPeak:
    peak_name = str(row["peak_name"])
    area = _float(row["area"])
    role = _peak_role(peak_name, str(row["known_or_unknown"]))
    return ChromatographyPeak(
        peak_id=f"{row['sample_id']}-{row['timepoint']}-inj{row['injection_number']}-{peak_name}",
        name=peak_name,
        role=role,
        retention_time_min=_float(row["retention_time_min"]),
        area=area,
        area_percent=(area / total_area * 100) if area is not None and total_area else None,
        height=_float(row["height"]),
        width_seconds=_float(row["width"]),
        tailing_factor=_float(row["tailing_factor"]),
        metadata={"known_or_unknown": str(row["known_or_unknown"])},
    )


def _peak_role(peak_name: str, known_or_unknown: str) -> str:
    normalized_name = peak_name.strip().lower()
    normalized_known = known_or_unknown.strip().lower()
    if normalized_name in PARENT_NAMES:
        return "parent"
    if normalized_known == "unknown":
        return "unknown"
    if "impurity" in normalized_name or normalized_known == "known":
        return "known_impurity"
    return normalized_known or "unknown"


def _timepoint_summary(measurements: list[ChromatographyMeasurement]) -> list[dict]:
    rows = []
    by_timepoint: dict[str, list[ChromatographyMeasurement]] = {}
    for measurement in measurements:
        by_timepoint.setdefault(measurement.timepoint or measurement.injection_id or "", []).append(measurement)

    for timepoint, group in by_timepoint.items():
        total_area = _mean([measurement.total_area for measurement in group])
        parent_area = _mean([_sum_peak_area(measurement, "parent") for measurement in group])
        known_area = _mean([_sum_peak_area(measurement, "known_impurity") for measurement in group])
        unknown_area = _mean([_sum_peak_area(measurement, "unknown") for measurement in group])
        parent_rt = _mean([_parent_retention_time(measurement) for measurement in group])
        rows.append(
            {
                "timepoint": timepoint,
                "total_area": total_area,
                "parent_area": parent_area,
                "parent_area_percent": _area_percent(parent_area, total_area),
                "known_impurity_area": known_area,
                "known_impurity_area_percent": _area_percent(known_area, total_area),
                "unknown_area": unknown_area,
                "unknown_area_percent": _area_percent(unknown_area, total_area),
                "parent_retention_time_min": parent_rt,
            }
        )

    return rows


def _latest_total_area_rsd(measurements: list[ChromatographyMeasurement], latest_timepoint: str) -> float | None:
    values = [measurement.total_area for measurement in measurements if measurement.timepoint == latest_timepoint and measurement.total_area is not None]
    if len(values) < 2:
        return None
    series = pd.Series(values, dtype=float)
    mean = float(series.mean())
    if mean == 0:
        return None
    return float(series.std(ddof=1) / mean * 100)


def _sum_peak_area(measurement: ChromatographyMeasurement, role: str) -> float | None:
    values = [peak.area for peak in measurement.peaks if peak.role == role and peak.area is not None]
    return sum(values) if values else 0.0


def _parent_retention_time(measurement: ChromatographyMeasurement) -> float | None:
    parent = next((peak for peak in measurement.peaks if peak.role == "parent"), None)
    return parent.retention_time_min if parent else None


def _area_percent(area: float | None, total_area: float | None) -> float | None:
    if area is None or total_area in (None, 0):
        return None
    return area / total_area * 100


def _percent_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline * 100


def _difference(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None:
        return None
    return current - baseline


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _float(value) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.iloc[0])


def _dedupe_observations(observations: list[Observation]) -> list[Observation]:
    deduped = []
    seen = set()
    for observation in observations:
        key = (observation.sample_name, observation.label, observation.evidence)
        if key in seen:
            continue
        deduped.append(observation)
        seen.add(key)
    return deduped
