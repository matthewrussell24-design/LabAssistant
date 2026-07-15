"""Presentation-neutral contracts and adapters for local DLS sample evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from labassistant.importers.dls import parse_dls_upload
from labassistant.measurements import measurement_from_dls_result
from labassistant.models import DistributionData, Measurement
from labassistant.quality import status_from_warnings


@runtime_checkable
class DLSSampleEvidence(Protocol):
    """Structural input accepted by in-process DLS application workflows.

    The protocol keeps application entry points independent of Streamlit and of
    the legacy ``ParsedSample`` name. ``data`` remains intentionally opaque at
    the contract level while compatibility workflows still use a pandas-backed
    local workspace implementation.
    """

    name: str
    file_name: str
    data: Any
    metadata: dict[str, str]
    metrics: dict[str, float | str | None]
    warnings: list[str]
    source_text: str
    measurement: Measurement


@dataclass
class DLSWorkspaceEvidence:
    """Mutable local-workspace adapter implementing ``DLSSampleEvidence``."""

    name: str
    file_name: str
    data: pd.DataFrame
    metadata: dict[str, str]
    metrics: dict[str, float | str | None]
    warnings: list[str]
    source_text: str
    measurement: Measurement


def parse_uploaded_file(uploaded_file: Any) -> DLSWorkspaceEvidence:
    parsed_dls = parse_dls_upload(uploaded_file)
    return DLSWorkspaceEvidence(
        name=parsed_dls.name,
        file_name=parsed_dls.file_name,
        data=parsed_dls.data,
        metadata=parsed_dls.metadata,
        metrics=parsed_dls.metrics,
        warnings=parsed_dls.warnings,
        source_text=parsed_dls.source_text,
        measurement=measurement_from_dls_result(parsed_dls),
    )


def sample_from_measurement(measurement: Measurement) -> DLSWorkspaceEvidence:
    distribution = _primary_distribution(measurement)
    data = _distribution_dataframe(distribution)
    warnings = [flag.label for flag in measurement.flags]
    metrics = {
        "Data Type": "Multi-file Measurement",
        "Z-Average": measurement.summary_metrics.z_average,
        "PDI": measurement.summary_metrics.pdi,
        "Max Z-Average": measurement.summary_metrics.max_z_average,
        "Max PDI": measurement.summary_metrics.max_pdi,
        "Measurement Count": measurement.summary_metrics.measurement_count,
        "Scattering Angles": _scattering_angles_label(measurement),
        "Primary Peak": measurement.derived_metrics.primary_peak_nm,
        "Secondary Peak": measurement.derived_metrics.secondary_peak_nm,
        "Peak Count": measurement.derived_metrics.peak_count,
        "Peak Width Ratio": measurement.derived_metrics.peak_width_ratio,
        "Peak Symmetry": measurement.derived_metrics.peak_symmetry,
        "Count Rate": measurement.summary_metrics.count_rate,
        "Tail Index": measurement.derived_metrics.tail_index_percent,
        "Width Ratio": measurement.derived_metrics.width_ratio,
        "Skewness": measurement.derived_metrics.skewness,
        "Aggregation Risk": measurement.derived_metrics.aggregation_risk,
        "Aggregation Index": measurement.derived_metrics.aggregation_index,
        "Quality Score": measurement.derived_metrics.quality_score,
        "D10": measurement.derived_metrics.d10_nm,
        "D50": measurement.derived_metrics.d50_nm,
        "D90": measurement.derived_metrics.d90_nm,
        "Diameter Column": "Diameter (nm)" if distribution and distribution.diameter_nm else None,
        "Intensity Column": "Intensity (%)" if distribution and distribution.intensity else None,
        "Volume Column": "Volume (%)" if distribution and distribution.volume else None,
        "Number Column": "Number (%)" if distribution and distribution.number else None,
        "Preferred Distribution": "Intensity (%)" if distribution and distribution.intensity else None,
        "Z-Average Column": None,
        "PDI Column": None,
        "Scattering Angle Column": None,
        "Measurement Date": measurement.metadata.measurement_datetime,
        "Correlogram Noise": measurement.derived_metrics.correlogram_noise_score,
    }
    return DLSWorkspaceEvidence(
        name=measurement.sample_name,
        file_name=", ".join(measurement.metadata.source_files),
        data=data,
        metadata=measurement.metadata.raw_fields,
        metrics=metrics,
        warnings=warnings,
        source_text=str(measurement.provenance),
        measurement=measurement,
    )


def sample_status(sample: DLSSampleEvidence) -> str:
    return status_from_warnings(sample.warnings)


def build_metrics_table(samples: list[DLSSampleEvidence]) -> pd.DataFrame:
    rows = []
    for sample in samples:
        rows.append(
            {
                "Sample": sample.name,
                "Status": sample_status(sample),
                "Data Type": sample.metrics["Data Type"],
                "Z-Average": sample.metrics["Z-Average"],
                "PDI": sample.metrics["PDI"],
                "Max Z-Average": sample.metrics["Max Z-Average"],
                "Max PDI": sample.metrics["Max PDI"],
                "Measurement Count": sample.metrics["Measurement Count"],
                "Scattering Angles": sample.metrics["Scattering Angles"],
                "Primary Peak": sample.metrics["Primary Peak"],
                "Secondary Peak": sample.metrics["Secondary Peak"],
                "Peak Count": sample.metrics.get("Peak Count"),
                "Peak Width Ratio": sample.metrics.get("Peak Width Ratio"),
                "Peak Symmetry": sample.metrics.get("Peak Symmetry"),
                "Count Rate": sample.metrics["Count Rate"],
                "Tail Index": sample.metrics["Tail Index"],
                "Width Ratio": sample.metrics["Width Ratio"],
                "Skewness": sample.metrics.get("Skewness"),
                "Aggregation Risk": sample.metrics.get("Aggregation Risk"),
                "Aggregation Index": sample.metrics.get("Aggregation Index"),
                "Quality Score": sample.metrics.get("Quality Score"),
                "D10": sample.metrics["D10"],
                "D50": sample.metrics["D50"],
                "D90": sample.metrics["D90"],
                "Measurement Date": sample.metrics["Measurement Date"],
                "Correlogram Noise": sample.metrics.get("Correlogram Noise"),
                "Warnings": ", ".join(sample.warnings) if sample.warnings else "None",
            }
        )
    return pd.DataFrame(rows)


def build_angle_table(samples: list[DLSSampleEvidence]) -> pd.DataFrame:
    """Return one row per sample per scattering angle."""

    columns = ["Sample", "Angle", "Position", "Measurements", "Replicates", "Z-Average", "PDI", "Max Z-Average", "Primary Peak", "D50"]
    rows = []
    for sample in samples:
        for angle in sample.measurement.angle_summaries:
            rows.append(
                {
                    "Sample": sample.name,
                    "Angle": angle.label,
                    "Position": angle.position,
                    "Measurements": angle.count,
                    "Replicates": angle.replicate_count,
                    "Z-Average": angle.z_average,
                    "PDI": angle.pdi,
                    "Max Z-Average": angle.max_z_average,
                    "Primary Peak": angle.primary_peak_nm,
                    "D50": angle.d50_nm,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def _scattering_angles_label(measurement: Measurement) -> str | None:
    angles = [summary.angle_degrees for summary in measurement.angle_summaries if summary.angle_degrees is not None]
    if angles:
        return ", ".join(f"{angle:g}°" for angle in angles)
    return measurement.metadata.scattering_angle


def _primary_distribution(measurement: Measurement) -> DistributionData | None:
    if "particle_size" in measurement.distributions:
        return measurement.distributions["particle_size"]
    if "intensity_replicate_1" in measurement.distributions:
        return measurement.distributions["intensity_replicate_1"]
    return next(iter(measurement.distributions.values()), None)


def _distribution_dataframe(distribution: DistributionData | None) -> pd.DataFrame:
    if distribution is None:
        return pd.DataFrame(columns=["Diameter (nm)", "Intensity (%)", "Volume (%)", "Number (%)"])

    length = max(
        len(distribution.diameter_nm),
        len(distribution.intensity),
        len(distribution.volume),
        len(distribution.number),
    )
    return pd.DataFrame(
        {
            "Diameter (nm)": _pad(distribution.diameter_nm, length),
            "Intensity (%)": _pad(distribution.intensity, length),
            "Volume (%)": _pad(distribution.volume, length),
            "Number (%)": _pad(distribution.number, length),
        }
    )


def _pad(values: list[float], length: int) -> list[float | None]:
    return values + [None] * (length - len(values))
