from __future__ import annotations


STATUS_NORMAL = "Normal"
STATUS_WATCH = "Watch"
STATUS_REVIEW = "Review"
PDI_WATCH_THRESHOLD = 0.30
PDI_REVIEW_THRESHOLD = 0.50
REVIEW_WARNINGS = ["High PDI", "Secondary peak", "Large-particle tail", "Broad distribution", "Dual-angle aggregation"]
SIGNAL_WARNINGS = ["High PDI", "Moderate PDI", "Secondary peak", "Large-particle tail", "Broad distribution", "Dual-angle aggregation"]


def classify_distribution_warnings(
    *,
    pdi: float | None,
    secondary_peak: float | None,
    tail_index: float | None,
    width_ratio: float | None,
    has_repeated_measurements: bool,
    has_distribution_columns: bool,
) -> list[str]:
    warnings = []

    if pdi is not None and pdi >= PDI_REVIEW_THRESHOLD:
        warnings.append("High PDI")
    elif pdi is not None and pdi >= PDI_WATCH_THRESHOLD and not has_repeated_measurements:
        warnings.append("Moderate PDI")
    if secondary_peak is not None:
        warnings.append("Secondary peak")
    if tail_index is not None and tail_index >= 5:
        warnings.append("Large-particle tail")
    if width_ratio is not None and width_ratio >= 8:
        warnings.append("Broad distribution")
    if not has_repeated_measurements and not has_distribution_columns:
        warnings.append("Distribution columns need review")

    return warnings


def status_from_warnings(warnings: list[str]) -> str:
    if any(warning in warnings for warning in REVIEW_WARNINGS):
        return STATUS_REVIEW
    if warnings:
        return STATUS_WATCH
    return STATUS_NORMAL


def flag_severity(warning: str) -> str:
    return "review" if warning in REVIEW_WARNINGS else "watch"
