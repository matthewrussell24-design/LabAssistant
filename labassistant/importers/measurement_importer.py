from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from labassistant.aggregation import assess_dual_angle_aggregation
from labassistant.importers.dls import (
    find_table_sections,
    read_excel_sections,
    section_to_dataframe,
)
from labassistant.importers.file_classifier import (
    CORRELOGRAM,
    INTENSITY_DISTRIBUTION,
    SUMMARY_EXPORT,
    ClassifiedFile,
    classify_uploaded_file,
)
from labassistant.importers.lot_grouper import LotFileGroup, group_files_by_lot, preview_rows
from labassistant.measurements import measurement_from_dls_result
from labassistant.metrics import (
    assess_aggregation_risk,
    calculate_distribution_percentiles,
    calculate_log_skewness,
    calculate_peak_symmetry,
    calculate_peak_width,
    calculate_quality_score,
    calculate_tail_index,
    calculate_width_ratio,
    count_peaks,
    find_local_peaks,
)
from labassistant.models import DistributionData, Measurement, MeasurementMetadata


@dataclass
class MultiFileImportPreview:
    groups: list[LotFileGroup]
    table: pd.DataFrame


@dataclass
class MeasurementImportResult:
    group: LotFileGroup
    measurement: Measurement | None
    errors: list[str]


def build_import_preview(uploaded_files) -> MultiFileImportPreview:
    classified_files = [classify_uploaded_file(uploaded_file) for uploaded_file in uploaded_files]
    groups = group_files_by_lot(classified_files)
    return MultiFileImportPreview(groups=groups, table=pd.DataFrame(preview_rows(groups)))


def import_measurement_groups(groups: list[LotFileGroup]) -> list[MeasurementImportResult]:
    return [import_measurement_group(group) for group in groups]


def import_measurement_group(group: LotFileGroup) -> MeasurementImportResult:
    measurement = Measurement(metadata=MeasurementMetadata(sample_name=group.lot))
    errors = []

    for classified_file in group.summary_files + group.intensity_files:
        if classified_file.parsed_result is None:
            errors.append(f"{classified_file.file_name}: {classified_file.error or 'could not parse DLS table'}")
            continue

        partial = measurement_from_dls_result(classified_file.parsed_result)
        partial.metadata.sample_name = group.lot
        partial.metadata.raw_fields.update(_filename_metadata(classified_file))
        measurement.merge(partial)

        if classified_file.file_type == INTENSITY_DISTRIBUTION:
            _merge_intensity_replicates(measurement, classified_file)

    for classified_file in group.correlogram_files:
        try:
            _merge_correlogram(measurement, classified_file)
        except (pd.errors.EmptyDataError, ValueError) as error:
            errors.append(f"{classified_file.file_name}: {error}")

    _refresh_correlogram_quality(measurement)
    _assign_replicates_to_angles(measurement)
    _refresh_distribution_metrics_from_intensity(measurement)
    _apply_dual_angle_aggregation(measurement)
    measurement.metadata.sample_name = group.lot
    measurement.metadata.source_files = list(dict.fromkeys([classified.file_name for classified in group.files]))
    measurement.provenance["import_status"] = group.status
    measurement.provenance["file_types"] = {classified.file_name: classified.file_type for classified in group.files}
    return MeasurementImportResult(group=group, measurement=measurement, errors=errors)


def _merge_intensity_replicates(measurement: Measurement, classified_file: ClassifiedFile) -> None:
    if classified_file.parsed_result is None:
        return

    data = classified_file.parsed_result.data
    diameter_column = classified_file.parsed_result.metrics.get("Diameter Column")
    intensity_columns = _signal_columns(data, "intensity")
    if not diameter_column or not intensity_columns:
        return

    replicates = []
    for index, intensity_column in enumerate(intensity_columns, start=1):
        distribution = DistributionData(
            diameter_nm=_numeric_values(data, str(diameter_column)),
            intensity=_numeric_values(data, intensity_column),
            source_columns={"diameter_nm": str(diameter_column), "intensity": intensity_column},
        )
        if distribution.diameter_nm and distribution.intensity:
            measurement.distributions[f"intensity_replicate_{index}"] = distribution
            replicates.append(
                {
                    "diameter_nm": distribution.diameter_nm,
                    "intensity": distribution.intensity,
                    "source_file": classified_file.file_name,
                    "source_column": intensity_column,
                }
            )

    if replicates:
        measurement.distributions["particle_size"] = measurement.distributions["intensity_replicate_1"]
        measurement.provenance.setdefault("intensity_replicates", []).extend(replicates)
        measurement.provenance["particle_size_source_file"] = classified_file.file_name


def _merge_correlogram(measurement: Measurement, classified_file: ClassifiedFile) -> None:
    tables = _tables_for_file(classified_file)
    if not tables:
        raise pd.errors.EmptyDataError("No table-like sections were found.")

    pairs = []
    for table in tables:
        time_columns = _columns_matching(table, ["time", "delay", "tau"])
        correlation_columns = _columns_matching(table, ["correlation", "correlogram", "g2", "acf"])
        if not time_columns or not correlation_columns:
            continue

        time_column = time_columns[0]
        for correlation_column in correlation_columns:
            working = table[[time_column, correlation_column]].dropna()
            for _, row in working.iterrows():
                time_value = pd.to_numeric(pd.Series([row[time_column]]), errors="coerce").dropna()
                correlation_value = pd.to_numeric(pd.Series([row[correlation_column]]), errors="coerce").dropna()
                if not time_value.empty and not correlation_value.empty:
                    measurement.correlogram.append(
                        {
                            "delay_time": float(time_value.iloc[0]),
                            "correlation": float(correlation_value.iloc[0]),
                            "replicate": float(len(pairs) + 1),
                        }
                    )
            pairs.append({"time_column": time_column, "correlation_column": correlation_column, "source_file": classified_file.file_name})

    if not pairs:
        raise ValueError("No correlogram replicate pairs were detected.")

    measurement.provenance.setdefault("correlogram_replicates", []).extend(pairs)


def _refresh_distribution_metrics_from_intensity(measurement: Measurement) -> None:
    distribution, source = _canonical_intensity_distribution(measurement)
    if distribution is None or not distribution.diameter_nm or not distribution.intensity:
        return

    data = pd.DataFrame({"Diameter (nm)": distribution.diameter_nm, "Intensity (%)": distribution.intensity})
    diameter_column = "Diameter (nm)"
    intensity_column = "Intensity (%)"
    peaks = find_local_peaks(data, diameter_column, intensity_column)
    percentiles = calculate_distribution_percentiles(data, diameter_column, intensity_column)

    derived = measurement.derived_metrics
    primary_peak = peaks[0]["diameter"] if peaks else None
    secondary_peak = peaks[1]["diameter"] if len(peaks) > 1 else None
    tail_index = calculate_tail_index(data, diameter_column, intensity_column)
    width_ratio = calculate_width_ratio(data, diameter_column, intensity_column)
    skewness = calculate_log_skewness(data, diameter_column, intensity_column)

    derived.primary_peak_nm = primary_peak
    derived.secondary_peak_nm = secondary_peak
    derived.peak_count = count_peaks(data, diameter_column, intensity_column)
    derived.peak_width_ratio = calculate_peak_width(data, diameter_column, intensity_column)
    derived.peak_symmetry = calculate_peak_symmetry(data, diameter_column, intensity_column)
    derived.d10_nm = percentiles["D10"]
    derived.d50_nm = percentiles["D50"]
    derived.d90_nm = percentiles["D90"]
    derived.tail_index_percent = tail_index
    derived.width_ratio = width_ratio
    derived.skewness = skewness
    derived.aggregation_risk = assess_aggregation_risk(
        tail_index=tail_index,
        secondary_peak_nm=secondary_peak,
        primary_peak_nm=primary_peak,
        pdi=measurement.summary_metrics.pdi,
        log_skewness=skewness,
        width_ratio=width_ratio,
    )
    derived.quality_score = calculate_quality_score(
        pdi=measurement.summary_metrics.pdi,
        tail_index=tail_index,
        width_ratio=width_ratio,
        secondary_peak_nm=secondary_peak,
        correlogram_noise=derived.correlogram_noise_score,
    )
    measurement.provenance["derived_metrics_source"] = source


def _canonical_intensity_distribution(measurement: Measurement) -> tuple[DistributionData | None, str]:
    """Select the intensity evidence used for lot-level derived metrics.

    Backscatter is the canonical sizing view when a dual-angle run is
    available; forward scatter remains separate evidence for aggregation.
    Single-angle runs use their angle-average. If angle assignment is not
    possible, all valid intensity replicates are averaged before falling back
    to the legacy particle-size curve.
    """
    angle_distributions = [
        (summary, measurement.distributions.get(f"angle_{summary.position or _angle_key(summary.angle_degrees)}"))
        for summary in measurement.angle_summaries
    ]
    angle_distributions = [
        (summary, distribution)
        for summary, distribution in angle_distributions
        if distribution is not None
    ]
    if angle_distributions:
        summary, distribution = max(
            angle_distributions,
            key=lambda item: (item[0].position == "back", item[0].angle_degrees or -math.inf),
        )
        return distribution, f"angle-averaged intensity distribution ({summary.label})"

    replicates = measurement.provenance.get("intensity_replicates", [])
    if replicates:
        averaged = _average_replicates(replicates)
        if not averaged.empty:
            return (
                DistributionData(
                    diameter_nm=averaged["d"].tolist(),
                    intensity=averaged["i"].tolist(),
                    source_columns={"diameter_nm": "Diameter (nm)", "intensity": "Intensity (%)"},
                ),
                f"mean intensity distribution ({len(replicates)} replicates)",
            )

    return measurement.distributions.get("particle_size"), "intensity distribution"


def _assign_replicates_to_angles(measurement: Measurement) -> None:
    """Group intensity replicates by scattering angle and derive per-angle curves.

    Replicate curves carry no angle label, but dual-angle runs separate cleanly
    by size (forward scatter reports larger diameters than back scatter). Each
    replicate is assigned to whichever angle summary its median size (D50) is
    closest to in log space, then replicates for an angle are averaged into one
    representative distribution used for that angle's primary peak and D50.
    """
    summaries = [summary for summary in measurement.angle_summaries if summary.z_average and summary.z_average > 0]
    replicates = measurement.provenance.get("intensity_replicates", [])
    if not summaries or not replicates:
        return

    buckets: dict[float, list[dict]] = {summary.angle_degrees: [] for summary in summaries}
    replicate_d50s: dict[float, list[float]] = {summary.angle_degrees: [] for summary in summaries}
    for replicate in replicates:
        frame = pd.DataFrame({"d": replicate["diameter_nm"], "i": replicate["intensity"]})
        center = calculate_distribution_percentiles(frame, "d", "i")["D50"]
        if center is None or center <= 0:
            continue
        nearest = min(summaries, key=lambda summary: abs(math.log10(center) - math.log10(summary.z_average)))
        buckets[nearest.angle_degrees].append(replicate)
        replicate_d50s[nearest.angle_degrees].append(float(center))

    assignment = {}
    for summary in summaries:
        grouped = buckets.get(summary.angle_degrees, [])
        if not grouped:
            continue
        averaged = _average_replicates(grouped)
        peaks = find_local_peaks(averaged, "d", "i")
        summary.primary_peak_nm = peaks[0]["diameter"] if peaks else None
        summary.d50_nm = calculate_distribution_percentiles(averaged, "d", "i")["D50"]
        summary.replicate_count = len(grouped)
        key = f"angle_{summary.position or _angle_key(summary.angle_degrees)}"
        measurement.distributions[key] = DistributionData(
            diameter_nm=averaged["d"].tolist(),
            intensity=averaged["i"].tolist(),
            source_columns={"diameter_nm": "Diameter (nm)", "intensity": "Intensity (%)"},
        )
        assignment[summary.label] = summary.replicate_count

    if assignment:
        measurement.provenance["angle_replicate_assignment"] = assignment
        position_by_angle = {summary.angle_degrees: (summary.position or _angle_key(summary.angle_degrees)) for summary in summaries}
        measurement.provenance["angle_replicate_d50s"] = {
            position_by_angle[angle]: values for angle, values in replicate_d50s.items() if values
        }


def _average_replicates(replicates: list[dict]) -> pd.DataFrame:
    base_diameters = replicates[0]["diameter_nm"]
    intensities = [
        replicate["intensity"]
        for replicate in replicates
        if len(replicate["diameter_nm"]) == len(base_diameters) and len(replicate["intensity"]) == len(base_diameters)
    ]
    if not intensities:
        intensities = [replicates[0]["intensity"]]
    count = len(intensities)
    averaged_intensity = [sum(values) / count for values in zip(*intensities)]
    return pd.DataFrame({"d": base_diameters, "i": averaged_intensity})


def _angle_key(angle_degrees: float | None) -> str:
    if angle_degrees is None:
        return "unknown"
    return str(angle_degrees).replace(".", "_")


def _apply_dual_angle_aggregation(measurement: Measurement) -> None:
    """Compute the dual-angle Aggregation Index and store it on the measurement."""
    assessment = assess_dual_angle_aggregation(measurement)
    measurement.derived_metrics.aggregation_index = assessment.aggregation_index
    measurement.provenance["dual_angle_aggregation"] = assessment.to_dict()
    if assessment.elevated:
        measurement.add_flag(
            "Dual-angle aggregation",
            severity="review",
            evidence=f"{assessment.category}: index {assessment.aggregation_index:.2f}, corroboration {assessment.corroboration_score}/{assessment.corroboration_max}",
        )


def _refresh_correlogram_quality(measurement: Measurement) -> None:
    """Estimate correlogram baseline noise, averaged across replicates.

    A DLS correlogram decays from its intercept toward a flat baseline near
    zero at long delay times. The scientifically meaningful "noise" is the
    residual scatter of that baseline, not the spread of the whole decay curve.
    For each replicate we take the points that have decayed below 10% of the
    intercept (excluding trailing zero padding) and measure their scatter, then
    average across replicates. Lower is cleaner.
    """
    if not measurement.correlogram:
        return

    data = pd.DataFrame(measurement.correlogram)
    if "correlation" not in data or "replicate" not in data:
        return

    replicate_noises = []
    for _, replicate_rows in data.groupby("replicate"):
        correlations = pd.to_numeric(replicate_rows["correlation"], errors="coerce").dropna()
        if correlations.empty:
            continue
        intercept = correlations.max()
        if intercept <= 0:
            continue
        baseline = correlations[(correlations < 0.10 * intercept) & (correlations != 0)]
        if len(baseline) >= 5:
            replicate_noises.append(float(baseline.std(ddof=0)))
        elif len(correlations) >= 2:
            replicate_noises.append(float(correlations.std(ddof=0)))

    if not replicate_noises:
        return

    measurement.derived_metrics.correlogram_noise_score = float(sum(replicate_noises) / len(replicate_noises))
    measurement.provenance["correlogram_quality_source"] = "correlogram"
    measurement.provenance["correlogram_replicate_count"] = len(replicate_noises)


def _tables_for_file(classified_file: ClassifiedFile) -> list[pd.DataFrame]:
    if classified_file.parsed_result is not None and classified_file.file_type != CORRELOGRAM:
        tables = [classified_file.parsed_result.data]
    else:
        tables = []

    file_name = classified_file.file_name.lower()
    if file_name.endswith((".xlsx", ".xls")):
        sections, _ = read_excel_sections(classified_file.file)
    else:
        sections = find_table_sections(classified_file.source_text)
    tables.extend(section_to_dataframe(section) for section in sections)
    return tables


def _signal_columns(data: pd.DataFrame, term: str) -> list[str]:
    return [column for column in data.columns if term in _normalize(column) and pd.api.types.is_numeric_dtype(data[column])]


def _columns_matching(data: pd.DataFrame, terms: list[str]) -> list[str]:
    numeric_columns = data.select_dtypes(include="number").columns.tolist()
    return [column for column in numeric_columns if any(term in _normalize(column) for term in terms)]


def _numeric_values(data: pd.DataFrame, column: str) -> list[float]:
    values = pd.to_numeric(data[column], errors="coerce").dropna()
    return [float(value) for value in values.tolist()]


def _filename_metadata(classified_file: ClassifiedFile) -> dict[str, str]:
    return {"Source file role": classified_file.file_type, "Source file name": classified_file.file_name}


def _normalize(value: str) -> str:
    return " ".join(str(value).lower().replace("_", " ").replace("-", " ").split())
