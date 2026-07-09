from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from labassistant.interpretation import format_metric
from labassistant.models import AngleSummary, FiltrationMeasurement, Measurement
from labassistant.view_models import ParsedSample


TREND_METRICS = {
    "Z-Average": "nm",
    "PDI": "",
    "Primary Peak": "nm",
    "D50": "nm",
    "Tail Index": "%",
    "Width Ratio": "",
    "Quality Score": "",
}

CIRCULATION_TIME_UNITS_TO_MINUTES = {
    "seconds": 1 / 60,
    "minutes": 1.0,
    "hours": 60.0,
}


@dataclass
class SeriesAnalysis:
    metric: str
    values: list[float]
    unit: str = ""
    labels: list[str] = field(default_factory=list)
    mean: float | None = None
    sd: float | None = None
    rsd_percent: float | None = None
    slope: float | None = None
    r_squared: float | None = None
    drift: str = "insufficient"
    change_point_index: int | None = None
    change_point_delta: float | None = None
    outlier_indices: list[int] = field(default_factory=list)
    outlier_method: str | None = None
    warning_limits: tuple[float, float] | None = None
    action_limits: tuple[float, float] | None = None

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def stable(self) -> bool:
        return self.drift == "stable" and not self.outlier_indices and self.change_point_index is None


@dataclass
class ForwardScatterPoint:
    sample: str
    circulation_time: float
    forward_z_average: float | None
    forward_pdi: float | None
    circulation_time_value: float | None = None
    circulation_time_unit: str | None = None


@dataclass
class FiltrationTrendPoint:
    sample: str
    difficulty_score: float
    forward_z_average: float | None
    forward_pdi: float | None
    circulation_time_minutes: float | None = None


@dataclass
class RelationshipAnalysis:
    metric: str
    unit: str
    points: list[ForwardScatterPoint]
    valid_count: int
    distinct_circulation_times: int
    pearson_r: float | None = None
    relationship: str | None = None
    message: str = ""


@dataclass
class ForwardScatterTrendAnalysis:
    points: list[ForwardScatterPoint]
    z_average: RelationshipAnalysis
    pdi: RelationshipAnalysis


@dataclass
class FiltrationTrendAnalysis:
    points: list[FiltrationTrendPoint]
    z_average: RelationshipAnalysis
    pdi: RelationshipAnalysis
    circulation_time: RelationshipAnalysis


def analyze_series(metric: str, values: list[float | int | None], unit: str = "", labels: list[str] | None = None) -> SeriesAnalysis:
    clean_values = [float(value) for value in values if value is not None and not pd.isna(value)]
    analysis = SeriesAnalysis(metric=metric, values=clean_values, unit=unit, labels=labels or [])
    if not clean_values:
        return analysis

    series = pd.Series(clean_values, dtype=float)
    analysis.mean = float(series.mean())
    analysis.sd = float(series.std(ddof=1)) if len(series) >= 2 else 0.0
    if analysis.mean and not math.isclose(analysis.mean, 0.0):
        analysis.rsd_percent = abs(analysis.sd / analysis.mean) * 100

    if len(series) >= 2 and analysis.sd is not None:
        analysis.warning_limits = (analysis.mean - 2 * analysis.sd, analysis.mean + 2 * analysis.sd)
        analysis.action_limits = (analysis.mean - 3 * analysis.sd, analysis.mean + 3 * analysis.sd)

    analysis.outlier_indices, analysis.outlier_method = detect_outliers(clean_values)

    if len(series) >= 3:
        analysis.slope, analysis.r_squared = regression_trend(clean_values)
        analysis.drift = classify_drift(analysis)
        analysis.change_point_index, analysis.change_point_delta = detect_change_point(clean_values)
    elif len(series) >= 2:
        analysis.drift = "stable" if not analysis.outlier_indices else "outlier"

    return analysis


def forward_angle_summary(measurement: Measurement) -> AngleSummary | None:
    """Return the forward-angle summary already parsed from DLS evidence."""
    positioned = [summary for summary in measurement.angle_summaries if summary.position == "forward"]
    if positioned:
        return positioned[0]

    angled = [
        summary
        for summary in measurement.angle_summaries
        if summary.angle_degrees is not None and summary.angle_degrees < 90
    ]
    if angled:
        return sorted(angled, key=lambda summary: summary.angle_degrees or 0)[0]
    return None


def build_forward_scatter_trend_analysis(
    samples: list[ParsedSample],
    circulation_times: dict[str, float | int | None],
) -> ForwardScatterTrendAnalysis:
    points: list[ForwardScatterPoint] = []
    for sample in samples:
        circulation_time = circulation_times.get(sample.name)
        if circulation_time is None or pd.isna(circulation_time):
            continue
        summary = forward_angle_summary(sample.measurement)
        points.append(
            ForwardScatterPoint(
                sample=sample.name,
                circulation_time=float(circulation_time),
                forward_z_average=summary.z_average if summary else None,
                forward_pdi=summary.pdi if summary else None,
                circulation_time_value=float(circulation_time),
                circulation_time_unit="minutes",
            )
        )

    return ForwardScatterTrendAnalysis(
        points=points,
        z_average=analyze_relationship("Forward Z-Average", "nm", points, "forward_z_average"),
        pdi=analyze_relationship("Forward PDI", "", points, "forward_pdi"),
    )


def build_forward_scatter_trend_analysis_from_measurements(samples: list[ParsedSample]) -> ForwardScatterTrendAnalysis:
    points = [
        point
        for sample in samples
        if (point := forward_scatter_point_from_measurement(sample)) is not None
    ]
    return ForwardScatterTrendAnalysis(
        points=points,
        z_average=analyze_relationship("Forward Z-Average", "nm", points, "forward_z_average"),
        pdi=analyze_relationship("Forward PDI", "", points, "forward_pdi"),
    )


def forward_scatter_point_from_measurement(sample: ParsedSample) -> ForwardScatterPoint | None:
    entry = circulation_time_from_measurement(sample.measurement)
    if entry is None:
        return None
    summary = forward_angle_summary(sample.measurement)
    return ForwardScatterPoint(
        sample=sample.name,
        circulation_time=entry["minutes"],
        circulation_time_value=entry["value"],
        circulation_time_unit=entry["unit"],
        forward_z_average=summary.z_average if summary else None,
        forward_pdi=summary.pdi if summary else None,
    )


def normalize_circulation_time(value: float | int, unit: str) -> float:
    if unit not in CIRCULATION_TIME_UNITS_TO_MINUTES:
        raise ValueError(f"Unsupported circulation time unit: {unit}")
    return float(value) * CIRCULATION_TIME_UNITS_TO_MINUTES[unit]


def apply_circulation_time(
    measurement: Measurement,
    value: float | int | None,
    unit: str | None,
    *,
    source: str = "manual_entry",
) -> None:
    if value is None or unit is None or pd.isna(value):
        measurement.provenance.pop("total_circulation_time", None)
        return
    minutes = normalize_circulation_time(float(value), unit)
    measurement.provenance["total_circulation_time"] = {
        "value": float(value),
        "unit": unit,
        "minutes": minutes,
        "source": source,
    }


def circulation_time_from_measurement(measurement: Measurement) -> dict[str, float | str] | None:
    entry = measurement.provenance.get("total_circulation_time")
    if not isinstance(entry, dict):
        return None
    try:
        minutes = float(entry["minutes"])
        value = float(entry.get("value", minutes))
    except (KeyError, TypeError, ValueError):
        return None
    unit = str(entry.get("unit") or "minutes")
    return {"minutes": minutes, "value": value, "unit": unit}


def apply_filtration_measurement(measurement: Measurement, filtration: FiltrationMeasurement | None) -> None:
    if filtration is None or filtration.difficulty_score is None:
        measurement.provenance.pop("filtration_follow_up", None)
        return
    measurement.provenance["filtration_follow_up"] = filtration.to_dict()


def filtration_measurement_from_provenance(measurement: Measurement) -> FiltrationMeasurement | None:
    payload = measurement.provenance.get("filtration_follow_up")
    if not isinstance(payload, dict):
        return None
    return FiltrationMeasurement(
        sample_name=str(payload.get("sample_name") or measurement.sample_name),
        difficulty_score=_optional_float(payload.get("difficulty_score")),
        filtration_time_minutes=_optional_float(payload.get("filtration_time_minutes")),
        pressure=_optional_float(payload.get("pressure")),
        pressure_unit=payload.get("pressure_unit"),
        filter_type=payload.get("filter_type"),
        clogging_observed=payload.get("clogging_observed"),
        notes=payload.get("notes"),
        source=str(payload.get("source") or "manual_entry"),
    )


def build_filtration_trend_analysis(samples: list[ParsedSample]) -> FiltrationTrendAnalysis:
    points: list[FiltrationTrendPoint] = []
    for sample in samples:
        filtration = filtration_measurement_from_provenance(sample.measurement)
        if filtration is None or filtration.difficulty_score is None:
            continue
        summary = forward_angle_summary(sample.measurement)
        circulation_time = circulation_time_from_measurement(sample.measurement)
        points.append(
            FiltrationTrendPoint(
                sample=sample.name,
                difficulty_score=filtration.difficulty_score,
                forward_z_average=summary.z_average if summary else None,
                forward_pdi=summary.pdi if summary else None,
                circulation_time_minutes=float(circulation_time["minutes"]) if circulation_time else None,
            )
        )

    return FiltrationTrendAnalysis(
        points=points,
        z_average=analyze_relationship("Filtration Difficulty vs Forward Z-Average", "", points, "forward_z_average", x_attribute="difficulty_score"),
        pdi=analyze_relationship("Filtration Difficulty vs Forward PDI", "", points, "forward_pdi", x_attribute="difficulty_score"),
        circulation_time=analyze_relationship(
            "Filtration Difficulty vs Circulation Time",
            "",
            points,
            "circulation_time_minutes",
            x_attribute="difficulty_score",
        ),
    )


def analyze_relationship(
    metric: str,
    unit: str,
    points: list[ForwardScatterPoint] | list[FiltrationTrendPoint],
    value_attribute: str,
    *,
    x_attribute: str = "circulation_time",
) -> RelationshipAnalysis:
    valid_points = [
        point
        for point in points
        if getattr(point, x_attribute) is not None
        and not pd.isna(getattr(point, x_attribute))
        and getattr(point, value_attribute) is not None
        and not pd.isna(getattr(point, value_attribute))
    ]
    distinct_x_values = len({float(getattr(point, x_attribute)) for point in valid_points})
    analysis = RelationshipAnalysis(
        metric=metric,
        unit=unit,
        points=valid_points,
        valid_count=len(valid_points),
        distinct_circulation_times=distinct_x_values,
    )

    if len(valid_points) < 3:
        analysis.message = f"At least 3 valid samples are needed to estimate correlation for {metric}."
        return analysis
    if distinct_x_values < 3:
        variable = "circulation times" if x_attribute == "circulation_time" else "x-axis values"
        analysis.message = f"At least 3 distinct {variable} are needed; repeated or missing values would make the statistic misleading."
        return analysis

    x_values = [float(getattr(point, x_attribute)) for point in valid_points]
    y_values = [float(getattr(point, value_attribute)) for point in valid_points]
    if len(set(y_values)) < 2:
        analysis.message = f"{metric} does not vary across the valid samples, so Pearson correlation is not informative."
        return analysis

    analysis.pearson_r = pearson_correlation(x_values, y_values)
    analysis.relationship = relationship_strength(analysis.pearson_r)
    analysis.message = (
        f"Pearson r = {analysis.pearson_r:.2f}, a {analysis.relationship} relationship in this dataset. "
        "This is correlation only, not evidence of causation."
    )
    return analysis


def pearson_correlation(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise ValueError("Pearson correlation requires paired vectors of equal length.")

    x = pd.Series(x_values, dtype=float)
    y = pd.Series(y_values, dtype=float)
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = math.sqrt(float((x_centered**2).sum()) * float((y_centered**2).sum()))
    if math.isclose(denominator, 0.0):
        raise ValueError("Pearson correlation requires variation in both variables.")
    return float((x_centered * y_centered).sum() / denominator)


def relationship_strength(correlation: float) -> str:
    magnitude = abs(correlation)
    if magnitude < 0.3:
        return "weak"
    if magnitude < 0.7:
        return "moderate"
    return "strong"


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def regression_trend(values: list[float]) -> tuple[float, float]:
    y = pd.Series(values, dtype=float)
    x = pd.Series(range(1, len(values) + 1), dtype=float)
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = float((x_centered**2).sum())
    if denominator == 0:
        return 0.0, 0.0
    slope = float((x_centered * y_centered).sum() / denominator)
    fitted = y.mean() + slope * x_centered
    total = float((y_centered**2).sum())
    residual = float(((y - fitted) ** 2).sum())
    r_squared = 0.0 if total == 0 else max(0.0, 1 - residual / total)
    return slope, r_squared


def classify_drift(analysis: SeriesAnalysis) -> str:
    if analysis.n < 3 or analysis.slope is None or analysis.r_squared is None:
        return "insufficient"
    if analysis.outlier_indices:
        return "outlier"
    first = analysis.values[0]
    last = analysis.values[-1]
    total_change = last - first
    relative_change = abs(total_change) / abs(first) if first else 0.0
    sd = analysis.sd or 0.0
    exceeds_noise = abs(total_change) >= max(sd * 1.5, abs(analysis.mean or 0) * 0.05)
    if analysis.r_squared >= 0.55 and relative_change >= 0.05 and exceeds_noise:
        return "increasing" if analysis.slope > 0 else "decreasing"
    return "stable"


def detect_change_point(values: list[float]) -> tuple[int | None, float | None]:
    if len(values) < 5:
        return None, None

    best_index = None
    best_score = 0.0
    best_delta = None
    overall_sd = float(pd.Series(values).std(ddof=1)) or 0.0
    if overall_sd == 0:
        return None, None

    for split_index in range(2, len(values) - 1):
        before = pd.Series(values[:split_index], dtype=float)
        after = pd.Series(values[split_index:], dtype=float)
        delta = float(after.mean() - before.mean())
        score = abs(delta) / overall_sd
        if score > best_score:
            best_index = split_index
            best_score = score
            best_delta = delta

    if best_index is not None and best_score >= 1.4:
        return best_index, best_delta
    return None, None


def detect_outliers(values: list[float]) -> tuple[list[int], str | None]:
    if len(values) < 3:
        return [], None

    series = pd.Series(values, dtype=float)
    median = float(series.median())
    absolute_deviation = (series - median).abs()
    mad = float(absolute_deviation.median())
    if mad > 0:
        modified_z = 0.6745 * (series - median).abs() / mad
        return [int(index) for index, score in modified_z.items() if score > 3.5], "MAD"

    sd = float(series.std(ddof=1))
    if sd == 0:
        return [], None
    mean = float(series.mean())
    z_scores = (series - mean).abs() / sd
    return [int(index) for index, score in z_scores.items() if score > 2.5], "Grubbs-style"


def replicate_analyses(measurement: Measurement) -> dict[str, SeriesAnalysis]:
    replicate_metrics = measurement.provenance.get("replicate_metrics") or {}
    analyses = {}
    for metric, values in replicate_metrics.items():
        unit = TREND_METRICS.get(metric, "")
        labels = [f"Rep {index}" for index in range(1, len(values) + 1)]
        analyses[metric] = analyze_series(metric, values, unit=unit, labels=labels)
    return analyses


def replicate_statistics_table(samples: list[ParsedSample]) -> pd.DataFrame:
    rows = []
    for sample in samples:
        for metric, analysis in replicate_analyses(sample.measurement).items():
            rows.append(
                {
                    "Sample": sample.name,
                    "Metric": metric,
                    "N": analysis.n,
                    "Mean": analysis.mean,
                    "SD": analysis.sd,
                    "%RSD": analysis.rsd_percent,
                    "Drift": analysis.drift,
                    "Outliers": ", ".join(analysis.labels[index] if index < len(analysis.labels) else str(index + 1) for index in analysis.outlier_indices) or "None",
                    "Change Point": f"after replicate {analysis.change_point_index}" if analysis.change_point_index else "None",
                }
            )
    return pd.DataFrame(rows)


def batch_metric_analyses(metrics: pd.DataFrame) -> dict[str, SeriesAnalysis]:
    analyses = {}
    for metric, unit in TREND_METRICS.items():
        if metric not in metrics:
            continue
        working = pd.DataFrame(
            {
                "Sample": metrics["Sample"].astype(str) if "Sample" in metrics else range(1, len(metrics) + 1),
                metric: pd.to_numeric(metrics[metric], errors="coerce"),
            }
        ).dropna(subset=[metric])
        values = working[metric].tolist()
        labels = working["Sample"].astype(str).tolist()
        analysis = analyze_series(metric, values, unit=unit, labels=labels)
        if analysis.n >= 2:
            analyses[metric] = analysis
    return analyses


def control_chart_table(samples: list[ParsedSample], metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, analysis in batch_metric_analyses(metrics).items():
        if not analysis.warning_limits or not analysis.action_limits:
            continue
        low_warning, high_warning = analysis.warning_limits
        low_action, high_action = analysis.action_limits
        for index, value in enumerate(analysis.values):
            label = analysis.labels[index] if index < len(analysis.labels) else str(index + 1)
            if value < low_action or value > high_action:
                zone = "Action"
            elif value < low_warning or value > high_warning:
                zone = "Warning"
            else:
                zone = "In control"
            rows.append(
                {
                    "Sample": label,
                    "Metric": metric,
                    "Value": value,
                    "Mean": analysis.mean,
                    "Warning Low": low_warning,
                    "Warning High": high_warning,
                    "Action Low": low_action,
                    "Action High": high_action,
                    "Zone": zone,
                }
            )
    return pd.DataFrame(rows)


def build_data_story(samples: list[ParsedSample], metrics: pd.DataFrame) -> dict[str, list[str]]:
    analyses = batch_metric_analyses(metrics)
    replicate_table = replicate_statistics_table(samples)

    what_changed = trend_sentences(analyses)
    attention = attention_sentences(analyses, replicate_table)
    stable = stable_sentences(analyses, replicate_table)

    if not what_changed:
        what_changed = ["No metric shows a strong monotonic shift across the imported order."]
    if not attention:
        attention = ["No control-limit breach, outlier, or change-point signal was detected in the available trend series."]
    if not stable:
        stable = ["There are not enough trendable replicate or batch series to confidently call stability."]

    return {
        "What Changed": what_changed[:4],
        "What Stayed Stable": stable[:4],
        "Needs Attention": attention[:4],
    }


def trend_sentences(analyses: dict[str, SeriesAnalysis]) -> list[str]:
    sentences = []
    for metric, analysis in analyses.items():
        if analysis.drift not in {"increasing", "decreasing"}:
            continue
        first = format_metric(analysis.values[0], analysis.unit, digits=3 if metric == "PDI" else 2)
        last = format_metric(analysis.values[-1], analysis.unit, digits=3 if metric == "PDI" else 2)
        sentences.append(f"{metric} is {analysis.drift} across sample order ({first} to {last}, R^2 {analysis.r_squared:.2f}).")
    return sentences


def stable_sentences(analyses: dict[str, SeriesAnalysis], replicate_table: pd.DataFrame) -> list[str]:
    sentences = []
    stable_metrics = [metric for metric, analysis in analyses.items() if analysis.stable]
    if stable_metrics:
        sentences.append(f"Batch-level {', '.join(stable_metrics[:3])} stayed within expected control variation.")

    if not replicate_table.empty:
        low_variability = replicate_table[pd.to_numeric(replicate_table["%RSD"], errors="coerce") <= 5]
        if not low_variability.empty:
            first = low_variability.iloc[0]
            sentences.append(f"{first['Sample']} has tight {first['Metric']} replicates (%RSD {first['%RSD']:.1f}).")
    return sentences


def attention_sentences(analyses: dict[str, SeriesAnalysis], replicate_table: pd.DataFrame) -> list[str]:
    sentences = []
    for metric, analysis in analyses.items():
        if analysis.outlier_indices:
            labels = [analysis.labels[index] if index < len(analysis.labels) else str(index + 1) for index in analysis.outlier_indices]
            sentences.append(f"{metric} has an outlier by {analysis.outlier_method}: {', '.join(labels)}.")
        if analysis.change_point_index is not None and analysis.change_point_delta is not None:
            sentences.append(f"{metric} shifts after item {analysis.change_point_index}; the post-shift mean changes by {format_metric(analysis.change_point_delta, analysis.unit)}.")

    if not replicate_table.empty:
        noisy = replicate_table[pd.to_numeric(replicate_table["%RSD"], errors="coerce") >= 10]
        if not noisy.empty:
            first = noisy.sort_values("%RSD", ascending=False).iloc[0]
            sentences.append(f"{first['Sample']} shows variable {first['Metric']} replicates (%RSD {first['%RSD']:.1f}).")
        replicate_drift = replicate_table[replicate_table["Drift"].isin(["increasing", "decreasing", "outlier"])]
        if not replicate_drift.empty:
            first = replicate_drift.iloc[0]
            sentences.append(f"{first['Sample']} replicate order is {first['Drift']} for {first['Metric']}.")
    return sentences
