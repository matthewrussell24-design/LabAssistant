from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from labassistant.interpretation import format_metric
from labassistant.models import Measurement
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
