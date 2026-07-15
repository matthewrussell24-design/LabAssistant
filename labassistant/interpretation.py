from __future__ import annotations

import pandas as pd

from labassistant.quality import STATUS_NORMAL, STATUS_REVIEW, STATUS_WATCH
from labassistant.dls_evidence import (
    DLSMeasurementMetrics,
    DLSSampleEvidence,
    measurement_metrics,
    sample_status,
)

ParsedSample = DLSSampleEvidence


def format_metric(value, unit: str = "", digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    if isinstance(value, str):
        return value
    if abs(value) >= 100:
        formatted = f"{value:,.0f}"
    else:
        formatted = f"{value:,.{digits}f}".rstrip("0").rstrip(".")
    return f"{formatted} {unit}".strip()


def review_evidence(sample: ParsedSample) -> str:
    """Compatibility wrapper for Measurement-first review evidence."""

    return review_evidence_from_metrics(measurement_metrics(sample.measurement))


def review_evidence_from_metrics(metrics: DLSMeasurementMetrics) -> str:
    """Format ordered warning evidence from an authoritative DLS projection."""

    evidence = []

    if "High PDI" in metrics.warnings:
        evidence.append(f"PDI {format_metric(metrics.pdi, digits=3)}")
    if "Moderate PDI" in metrics.warnings:
        evidence.append(f"PDI {format_metric(metrics.pdi, digits=3)}")
    if "Secondary peak" in metrics.warnings:
        evidence.append(
            f"secondary peak {format_metric(metrics.secondary_peak_nm, 'nm')}"
        )
    if "Large-particle tail" in metrics.warnings:
        evidence.append(
            f"tail index {format_metric(metrics.tail_index_percent, '%')}"
        )
    if "Broad distribution" in metrics.warnings:
        evidence.append(f"D90/D10 {format_metric(metrics.width_ratio, digits=2)}")
    if "Dual-angle aggregation" in metrics.warnings:
        index = metrics.aggregation_index
        if index is not None and not pd.isna(index):
            evidence.append(f"dual-angle aggregation index {format_metric(index, digits=2)}")
        else:
            evidence.append("elevated dual-angle aggregation signal")
    if "Distribution columns need review" in metrics.warnings:
        evidence.append("distribution columns were not identified")

    return ", ".join(evidence) if evidence else "No metric evidence found"


def describe_metric_range(values: pd.Series, unit: str = "", digits: int = 2) -> str:
    clean_values = pd.to_numeric(values, errors="coerce").dropna()
    if clean_values.empty:
        return "not enough parsed values"

    if len(clean_values) == 1:
        return format_metric(float(clean_values.iloc[0]), unit, digits)

    return f"{format_metric(float(clean_values.min()), unit, digits)} to {format_metric(float(clean_values.max()), unit, digits)}"


def sample_label_list(samples: list[ParsedSample], limit: int = 4) -> str:
    names = [sample.name for sample in samples]
    if not names:
        return "none"
    if len(names) <= limit:
        return ", ".join(names)
    return f"{', '.join(names[:limit])}, and {len(names) - limit} more"


def metric_extreme(metrics: pd.DataFrame, metric: str, kind: str) -> pd.Series | None:
    clean = metrics.copy()
    clean[metric] = pd.to_numeric(clean[metric], errors="coerce")
    clean = clean.dropna(subset=[metric])

    if clean.empty:
        return None

    index = clean[metric].idxmax() if kind == "max" else clean[metric].idxmin()
    return clean.loc[index]


def metric_median(metrics: pd.DataFrame, metric: str) -> float | None:
    values = pd.to_numeric(metrics[metric], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.median())


def sample_attention_score(sample: ParsedSample, medians: dict[str, float | None]) -> float:
    score = 0.0

    if sample_status(sample) == STATUS_REVIEW:
        score += 60
    elif sample_status(sample) == STATUS_WATCH:
        score += 25

    pdi = sample.metrics["PDI"]
    if pdi is not None and not pd.isna(pdi):
        score += min(float(pdi) * 55, 35)
        median_pdi = medians.get("PDI")
        if median_pdi is not None and float(pdi) >= median_pdi + 0.10:
            score += 12

    tail_index = sample.metrics["Tail Index"]
    if tail_index is not None and not pd.isna(tail_index):
        score += min(float(tail_index) * 2.5, 30)
        median_tail = medians.get("Tail Index")
        if median_tail is not None and float(tail_index) >= median_tail + 3:
            score += 10

    width_ratio = sample.metrics["Width Ratio"]
    if width_ratio is not None and not pd.isna(width_ratio):
        score += min(float(width_ratio) * 1.4, 18)

    if sample.metrics["Secondary Peak"] is not None and not pd.isna(sample.metrics["Secondary Peak"]):
        score += 18

    z_average = sample.metrics["Z-Average"]
    median_z = medians.get("Z-Average")
    if z_average is not None and median_z is not None and median_z > 0 and not pd.isna(z_average):
        fold_change = max(float(z_average) / median_z, median_z / float(z_average)) if float(z_average) > 0 else 1
        if fold_change >= 1.25:
            score += min((fold_change - 1) * 18, 22)

    if "Distribution columns need review" in sample.warnings:
        score += 18

    return score


def build_attention_table(samples: list[ParsedSample], metrics: pd.DataFrame) -> pd.DataFrame:
    medians = {
        "Z-Average": metric_median(metrics, "Z-Average"),
        "PDI": metric_median(metrics, "PDI"),
        "Tail Index": metric_median(metrics, "Tail Index"),
    }
    rows = []

    for sample in samples:
        score = sample_attention_score(sample, medians)
        rows.append(
            {
                "Sample": sample.name,
                "Status": sample_status(sample),
                "Attention Score": score,
                "Reason": review_evidence(sample) if sample.warnings else "No warning thresholds crossed",
                "Warnings": ", ".join(sample.warnings) if sample.warnings else "None",
            }
        )

    return pd.DataFrame(rows).sort_values(["Attention Score", "Sample"], ascending=[False, True])


def build_change_findings(metrics: pd.DataFrame) -> list[str]:
    findings = []
    checks = [
        ("Z-Average", "Z-average", "nm", 1.25),
        ("Primary Peak", "primary peak", "nm", 1.5),
        ("PDI", "PDI", "", None),
        ("Tail Index", "large-particle tail", "%", None),
    ]

    for metric, label, unit, fold_threshold in checks:
        highest = metric_extreme(metrics, metric, "max")
        lowest = metric_extreme(metrics, metric, "min")
        if highest is None or lowest is None or highest["Sample"] == lowest["Sample"]:
            continue

        high_value = highest[metric]
        low_value = lowest[metric]
        if pd.isna(high_value) or pd.isna(low_value):
            continue

        if fold_threshold and low_value > 0 and high_value < low_value * fold_threshold:
            continue
        if metric == "PDI" and high_value - low_value < 0.10:
            continue
        if metric == "Tail Index" and high_value - low_value < 3:
            continue

        findings.append(
            f"{label} differs most between {lowest['Sample']} ({format_metric(low_value, unit, digits=3 if metric == 'PDI' else 2)}) and {highest['Sample']} ({format_metric(high_value, unit, digits=3 if metric == 'PDI' else 2)})."
        )

    return findings[:3]


def build_decision_brief(samples: list[ParsedSample], metrics: pd.DataFrame) -> dict[str, str | list[str] | pd.DataFrame]:
    attention = build_attention_table(samples, metrics)
    flagged = attention[attention["Status"] != STATUS_NORMAL]
    normal = attention[attention["Status"] == STATUS_NORMAL]
    best_pool = normal if not normal.empty else attention
    best = best_pool.sort_values(["Attention Score", "Sample"], ascending=[True, True]).iloc[0]
    worst = attention.iloc[0]

    review = attention[attention["Status"] == STATUS_REVIEW]
    unusual = build_change_findings(metrics)
    if not unusual:
        unusual = ["No large between-sample shifts were detected in the parsed metrics."]

    if not flagged.empty:
        next_check = f"Inspect {worst['Sample']} first: {worst['Reason']}."
    elif len(samples) > 1:
        next_check = f"Use {best['Sample']} as the provisional reference and compare overlays for subtle size shifts."
    else:
        next_check = "Review the raw curve and instrument metadata before treating this as a clean pass."

    return {
        "best": f"{best['Sample']} ({best['Status']})",
        "worst": f"{worst['Sample']} ({worst['Status']})",
        "flagged": f"{len(flagged)} of {len(samples)}",
        "review": sample_label_list([sample for sample in samples if sample.name in review["Sample"].tolist()]) if not review.empty else "none",
        "next_check": next_check,
        "unusual": unusual,
        "attention": attention,
    }


def build_ai_summary(samples: list[ParsedSample], metrics: pd.DataFrame) -> dict[str, list[str]]:
    decision = build_decision_brief(samples, metrics)
    flagged = [sample for sample in samples if sample_status(sample) != STATUS_NORMAL]
    normal_samples = [sample for sample in samples if sample_status(sample) == STATUS_NORMAL]
    flagged_reasons = [f"{sample.name}: {review_evidence(sample)}" for sample in flagged[:5]]

    main_finding = [
        f"Best candidate: {decision['best']}.",
        f"Needs most attention: {decision['worst']}.",
        f"Flagged samples: {decision['flagged']}.",
    ]

    samples_needing_review = flagged_reasons or ["No samples crossed the current warning thresholds."]
    why_flagged = decision["unusual"]
    what_normal = [
        f"Normal samples: {sample_label_list(normal_samples)}." if normal_samples else "No sample is fully clean by the current rules.",
        f"Z-average range: {describe_metric_range(metrics['Z-Average'], 'nm')}.",
        f"PDI range: {describe_metric_range(metrics['PDI'], digits=3)}.",
    ]
    suggested_next_check = [str(decision["next_check"])]

    return {
        "Main Finding": main_finding,
        "Samples Needing Review": samples_needing_review,
        "Why They Were Flagged": why_flagged,
        "What Looks Normal": what_normal,
        "Suggested Next Check": suggested_next_check,
    }


def build_data_analysis(samples: list[ParsedSample], metrics: pd.DataFrame) -> dict[str, list[str]]:
    flagged = [sample for sample in samples if sample_status(sample) != STATUS_NORMAL]
    review_samples = [sample for sample in samples if sample_status(sample) == STATUS_REVIEW]

    highest_z = metric_extreme(metrics, "Z-Average", "max")
    lowest_z = metric_extreme(metrics, "Z-Average", "min")
    highest_pdi = metric_extreme(metrics, "PDI", "max")
    lowest_pdi = metric_extreme(metrics, "PDI", "min")
    highest_tail = metric_extreme(metrics, "Tail Index", "max")
    highest_width = metric_extreme(metrics, "Width Ratio", "max")
    highest_peak = metric_extreme(metrics, "Primary Peak", "max")
    lowest_peak = metric_extreme(metrics, "Primary Peak", "min")

    median_z = metric_median(metrics, "Z-Average")
    median_pdi = metric_median(metrics, "PDI")
    median_tail = metric_median(metrics, "Tail Index")

    main_findings = []
    if flagged:
        main_findings.append(f"The dataset is not completely uniform: {len(flagged)} of {len(samples)} samples are flagged, with {sample_label_list(review_samples or flagged)} driving most of the concern.")
    else:
        main_findings.append(f"Across these {len(samples)} samples, the parsed metrics look broadly consistent; none crossed the app's warning thresholds.")

    if highest_z is not None and lowest_z is not None and highest_z["Sample"] != lowest_z["Sample"]:
        main_findings.append(
            f"Particle size is largest in {highest_z['Sample']} ({format_metric(highest_z['Z-Average'], 'nm')}) and smallest in {lowest_z['Sample']} ({format_metric(lowest_z['Z-Average'], 'nm')})."
        )
    elif highest_z is not None:
        main_findings.append(f"The typical particle size centers around {format_metric(highest_z['Z-Average'], 'nm')} for the parsed sample.")

    if highest_pdi is not None and lowest_pdi is not None and highest_pdi["Sample"] != lowest_pdi["Sample"]:
        main_findings.append(
            f"Uniformity varies most between {lowest_pdi['Sample']} (PDI {format_metric(lowest_pdi['PDI'], digits=3)}, cleaner) and {highest_pdi['Sample']} (PDI {format_metric(highest_pdi['PDI'], digits=3)}, more mixed)."
        )

    drivers = []
    if highest_tail is not None and pd.notna(highest_tail["Tail Index"]):
        if highest_tail["Tail Index"] >= 5:
            drivers.append(f"{highest_tail['Sample']} has the strongest large-particle tail at {format_metric(highest_tail['Tail Index'], '%')}, so it is the main sample to inspect for aggregates or oversized material.")
        elif highest_tail["Tail Index"] > 0:
            drivers.append(f"The largest tail signal is {format_metric(highest_tail['Tail Index'], '%')} in {highest_tail['Sample']}, which is below the current review threshold.")

    if highest_width is not None and pd.notna(highest_width["Width Ratio"]):
        if highest_width["Width Ratio"] >= 8:
            drivers.append(f"{highest_width['Sample']} has the broadest distribution, so its particles are spread across the widest size range.")
        elif len(samples) > 1:
            drivers.append(f"Distribution width is most pronounced in {highest_width['Sample']}, but it does not cross the broad-distribution threshold.")

    if highest_peak is not None and lowest_peak is not None and highest_peak["Sample"] != lowest_peak["Sample"]:
        drivers.append(
            f"The main peak shifts from {format_metric(lowest_peak['Primary Peak'], 'nm')} in {lowest_peak['Sample']} to {format_metric(highest_peak['Primary Peak'], 'nm')} in {highest_peak['Sample']}, which suggests the dominant particle population is not identical across samples."
        )

    if not drivers:
        drivers.append("No single metric is strongly pulling the dataset away from the others; the samples appear similar in the parsed values.")

    confidence = []
    if median_z is not None:
        confidence.append(f"Median Z-average is {format_metric(median_z, 'nm')}, which is a useful center point for judging which samples are unusually small or large.")
    if median_pdi is not None:
        confidence.append(f"Median PDI is {format_metric(median_pdi, digits=3)}; samples much above that are the less uniform ones.")
    if median_tail is not None:
        confidence.append(f"Median large-particle tail is {format_metric(median_tail, '%')}; values above that make the far-right side of the curve more important.")

    missing_distribution = [sample for sample in samples if not sample.metrics["Diameter Column"] or not sample.metrics["Preferred Distribution"]]
    if missing_distribution:
        confidence.append(f"Interpret the chart-based analysis cautiously for {sample_label_list(missing_distribution)} because the app could not confidently identify the distribution columns.")
    else:
        confidence.append("The analysis is based on parsed instrument exports, so it should be treated as a screening interpretation and checked against the raw curves.")

    return {
        "Main Finding": main_findings,
        "What Is Driving It": drivers,
        "How To Judge It": confidence,
    }
