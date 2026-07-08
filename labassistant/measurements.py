from __future__ import annotations

import pandas as pd

from labassistant.importers.dls import ParsedDLSResult, normalize_label
from labassistant.models import (
    AngleSummary,
    DerivedMetrics,
    DistributionData,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    SummaryMetrics,
)
from labassistant.quality import flag_severity, status_from_warnings


def metadata_value(metadata: dict[str, str], terms: list[str]) -> str | None:
    for key, value in metadata.items():
        label = normalize_label(key)
        if all(term in label for term in terms):
            return value
    return None


def metric_float(metrics: dict[str, float | str | None], key: str) -> float | None:
    value = metrics.get(key)
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_int(metrics: dict[str, float | str | None], key: str) -> int | None:
    value = metric_float(metrics, key)
    return int(value) if value is not None else None


def numeric_column_values(data: pd.DataFrame, column: str | None) -> list[float]:
    if not column or column not in data:
        return []
    values = pd.to_numeric(data[column], errors="coerce").dropna()
    return [float(value) for value in values.tolist()]


def warning_evidence(metrics: dict[str, float | str | None], warning: str) -> str | None:
    if warning in {"High PDI", "Moderate PDI"}:
        pdi = metric_float(metrics, "PDI")
        return f"PDI {pdi:.3g}" if pdi is not None else None
    if warning == "Secondary peak":
        peak = metric_float(metrics, "Secondary Peak")
        return f"secondary peak {peak:.3g} nm" if peak is not None else None
    if warning == "Large-particle tail":
        tail_index = metric_float(metrics, "Tail Index")
        return f"tail index {tail_index:.3g}%" if tail_index is not None else None
    if warning == "Broad distribution":
        width_ratio = metric_float(metrics, "Width Ratio")
        return f"D90/D10 {width_ratio:.3g}" if width_ratio is not None else None
    if warning == "Distribution columns need review":
        return "distribution columns were not identified"
    return None


def angle_label(position: str | None, angle_degrees: float | None) -> str:
    prefix = position.capitalize() if position else "Angle"
    if angle_degrees is None:
        return prefix
    return f"{prefix} {angle_degrees:g}°"


def angle_summaries_from_result(result: ParsedDLSResult) -> list[AngleSummary]:
    summaries = []
    for entry in result.angle_summaries:
        angle_degrees = entry.get("angle_degrees")
        position = entry.get("position")
        summaries.append(
            AngleSummary(
                label=angle_label(position, angle_degrees),
                angle_degrees=angle_degrees,
                position=position,
                count=entry.get("count"),
                z_average=entry.get("z_average"),
                pdi=entry.get("pdi"),
                max_z_average=entry.get("max_z_average"),
            )
        )
    return summaries


def measurement_from_dls_result(result: ParsedDLSResult) -> Measurement:
    metadata = MeasurementMetadata(
        sample_name=result.name,
        source_files=[result.file_name],
        measurement_datetime=str(result.metrics["Measurement Date"]) if result.metrics.get("Measurement Date") else None,
        instrument=metadata_value(result.metadata, ["instrument"]),
        operator=metadata_value(result.metadata, ["operator"]),
        temperature=metadata_value(result.metadata, ["temperature"]),
        scattering_angle=str(result.metrics["Scattering Angles"]) if result.metrics.get("Scattering Angles") else metadata_value(result.metadata, ["scattering"]),
        method=metadata_value(result.metadata, ["sop"]) or metadata_value(result.metadata, ["method"]),
        raw_fields=dict(result.metadata),
    )

    peak_sizes = [
        value
        for value in [
            metric_float(result.metrics, "Primary Peak"),
            metric_float(result.metrics, "Secondary Peak"),
        ]
        if value is not None
    ]
    summary_metrics = SummaryMetrics(
        z_average=metric_float(result.metrics, "Z-Average"),
        pdi=metric_float(result.metrics, "PDI"),
        peak_sizes=peak_sizes,
        count_rate=metric_float(result.metrics, "Count Rate"),
        measurement_count=metric_int(result.metrics, "Measurement Count"),
        max_z_average=metric_float(result.metrics, "Max Z-Average"),
        max_pdi=metric_float(result.metrics, "Max PDI"),
    )

    distribution = DistributionData(
        diameter_nm=numeric_column_values(result.data, str(result.metrics["Diameter Column"]) if result.metrics.get("Diameter Column") else None),
        intensity=numeric_column_values(result.data, str(result.metrics["Intensity Column"]) if result.metrics.get("Intensity Column") else None),
        volume=numeric_column_values(result.data, str(result.metrics["Volume Column"]) if result.metrics.get("Volume Column") else None),
        number=numeric_column_values(result.data, str(result.metrics["Number Column"]) if result.metrics.get("Number Column") else None),
        source_columns={
            key: str(value)
            for key, value in {
                "diameter_nm": result.metrics.get("Diameter Column"),
                "intensity": result.metrics.get("Intensity Column"),
                "volume": result.metrics.get("Volume Column"),
                "number": result.metrics.get("Number Column"),
            }.items()
            if value
        },
    )
    distributions = {"particle_size": distribution} if distribution.diameter_nm and distribution.has_any_signal() else {}

    derived_metrics = DerivedMetrics(
        primary_peak_nm=metric_float(result.metrics, "Primary Peak"),
        secondary_peak_nm=metric_float(result.metrics, "Secondary Peak"),
        peak_count=metric_int(result.metrics, "Peak Count"),
        peak_width_ratio=metric_float(result.metrics, "Peak Width Ratio"),
        peak_symmetry=metric_float(result.metrics, "Peak Symmetry"),
        d10_nm=metric_float(result.metrics, "D10"),
        d50_nm=metric_float(result.metrics, "D50"),
        d90_nm=metric_float(result.metrics, "D90"),
        tail_index_percent=metric_float(result.metrics, "Tail Index"),
        width_ratio=metric_float(result.metrics, "Width Ratio"),
        skewness=metric_float(result.metrics, "Skewness"),
        aggregation_risk=result.metrics.get("Aggregation Risk") or status_from_warnings(result.warnings),
        quality_score=metric_float(result.metrics, "Quality Score"),
    )

    return Measurement(
        metadata=metadata,
        summary_metrics=summary_metrics,
        distributions=distributions,
        derived_metrics=derived_metrics,
        angle_summaries=angle_summaries_from_result(result),
        flags=[
            MeasurementFlag(label=warning, severity=flag_severity(warning), evidence=warning_evidence(result.metrics, warning))
            for warning in result.warnings
        ],
        provenance={
            "data_type": result.metrics.get("Data Type"),
            "preferred_distribution": result.metrics.get("Preferred Distribution"),
            "replicate_metrics": result.replicate_metrics,
            "source_text_preview": result.source_text[:1000],
        },
    )
