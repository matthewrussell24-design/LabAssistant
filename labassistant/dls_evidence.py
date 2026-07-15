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


@runtime_checkable
class DLSRawPointTableSource(Protocol):
    """Opaque vendor table surface required by raw inspection only."""

    columns: Any

    def itertuples(self, *, index: bool, name: None) -> Any: ...


@runtime_checkable
class DLSRawSampleSource(Protocol):
    """Minimal sample adapter for lossless raw DLS inspection."""

    name: str
    data: DLSRawPointTableSource
    metadata: dict[str, str]
    source_text: str


@runtime_checkable
class DLSRawFileDiagnosticSource(Protocol):
    """One classified source-file diagnostic supplied by an importer adapter."""

    file_name: str
    file_type: str
    source_text: str | None
    error: str | None


@runtime_checkable
class DLSRawGroupDiagnosticSource(Protocol):
    """One lot and its original classified files in importer order."""

    lot: str
    files: Any


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


@dataclass(frozen=True)
class DLSMeasurementMetrics:
    """Pandas-free metric and status projection from one DLS Measurement."""

    data_type: str
    z_average_nm: float | None
    pdi: float | None
    max_z_average_nm: float | None
    max_pdi: float | None
    measurement_count: int | None
    scattering_angles: str | None
    primary_peak_nm: float | None
    secondary_peak_nm: float | None
    peak_count: int | None
    peak_width_ratio: float | None
    peak_symmetry: float | None
    count_rate: float | None
    tail_index_percent: float | None
    width_ratio: float | None
    skewness: float | None
    aggregation_risk: str | None
    aggregation_index: float | None
    quality_score: float | None
    d10_nm: float | None
    d50_nm: float | None
    d90_nm: float | None
    measurement_date: str | None
    correlogram_noise_score: float | None
    has_distribution_evidence: bool
    warnings: tuple[str, ...]
    status: str


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
    measurement.provenance["workspace_data_type"] = "Multi-file Measurement"
    distribution = primary_distribution(measurement)
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
    return measurement_metrics(sample.measurement).status


def measurement_metrics(measurement: Measurement) -> DLSMeasurementMetrics:
    """Project authoritative Measurement fields into established DLS metrics."""

    if not isinstance(measurement, Measurement):
        raise TypeError("DLS metrics require a Measurement")
    warnings = tuple(str(flag.label) for flag in measurement.flags)
    has_distribution_evidence = any(
        bool(distribution.diameter_nm) and distribution.has_any_signal()
        for distribution in measurement.distributions.values()
    )
    return DLSMeasurementMetrics(
        data_type=str(
            measurement.provenance.get("workspace_data_type")
            or measurement.provenance.get("data_type")
            or "Multi-file Measurement"
        ),
        z_average_nm=measurement.summary_metrics.z_average,
        pdi=measurement.summary_metrics.pdi,
        max_z_average_nm=measurement.summary_metrics.max_z_average,
        max_pdi=measurement.summary_metrics.max_pdi,
        measurement_count=measurement.summary_metrics.measurement_count,
        scattering_angles=_scattering_angles_label(measurement),
        primary_peak_nm=measurement.derived_metrics.primary_peak_nm,
        secondary_peak_nm=measurement.derived_metrics.secondary_peak_nm,
        peak_count=measurement.derived_metrics.peak_count,
        peak_width_ratio=measurement.derived_metrics.peak_width_ratio,
        peak_symmetry=measurement.derived_metrics.peak_symmetry,
        count_rate=measurement.summary_metrics.count_rate,
        tail_index_percent=measurement.derived_metrics.tail_index_percent,
        width_ratio=measurement.derived_metrics.width_ratio,
        skewness=measurement.derived_metrics.skewness,
        aggregation_risk=measurement.derived_metrics.aggregation_risk,
        aggregation_index=measurement.derived_metrics.aggregation_index,
        quality_score=measurement.derived_metrics.quality_score,
        d10_nm=measurement.derived_metrics.d10_nm,
        d50_nm=measurement.derived_metrics.d50_nm,
        d90_nm=measurement.derived_metrics.d90_nm,
        measurement_date=measurement.metadata.measurement_datetime,
        correlogram_noise_score=measurement.derived_metrics.correlogram_noise_score,
        has_distribution_evidence=has_distribution_evidence,
        warnings=warnings,
        status=status_from_warnings(list(warnings)),
    )


def build_metrics_table(samples: list[DLSSampleEvidence]) -> pd.DataFrame:
    rows = []
    for sample in samples:
        projected = measurement_metrics(sample.measurement)
        rows.append(
            {
                "Sample": sample.name,
                "Status": projected.status,
                "Data Type": projected.data_type,
                "Z-Average": projected.z_average_nm,
                "PDI": projected.pdi,
                "Max Z-Average": projected.max_z_average_nm,
                "Max PDI": projected.max_pdi,
                "Measurement Count": projected.measurement_count,
                "Scattering Angles": projected.scattering_angles,
                "Primary Peak": projected.primary_peak_nm,
                "Secondary Peak": projected.secondary_peak_nm,
                "Peak Count": projected.peak_count,
                "Peak Width Ratio": projected.peak_width_ratio,
                "Peak Symmetry": projected.peak_symmetry,
                "Count Rate": projected.count_rate,
                "Tail Index": projected.tail_index_percent,
                "Width Ratio": projected.width_ratio,
                "Skewness": projected.skewness,
                "Aggregation Risk": projected.aggregation_risk,
                "Aggregation Index": projected.aggregation_index,
                "Quality Score": projected.quality_score,
                "D10": projected.d10_nm,
                "D50": projected.d50_nm,
                "D90": projected.d90_nm,
                "Measurement Date": projected.measurement_date,
                "Correlogram Noise": projected.correlogram_noise_score,
                "Warnings": ", ".join(projected.warnings) if projected.warnings else "None",
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


def primary_distribution(measurement: Measurement) -> DistributionData | None:
    """Return the canonical distribution used by compatibility projections."""

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
