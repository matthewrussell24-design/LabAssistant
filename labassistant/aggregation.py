"""Dual-angle aggregation detection.

Implements the enhanced protein-aggregation method from Malvern Panalytical's
application notes AN101104 ("Enhanced Protein Aggregation Detection Using Dual
Angle Dynamic Light Scattering") and AN140527 ("Enhanced Aggregate Detection:
Monitoring Protein Stability Using Dual Angle Light Scattering").

Forward scatter (~12.8°) is far more sensitive to a small number of large
species than backscatter (~173°), because large particles scatter strongly in
the forward direction. When aggregates or oversized material appear, the
forward-angle Z-average inflates relative to backscatter. The Aggregation Index
captures that gap:

    Aggregation Index = Z-average(forward) / Z-average(backscatter) - 1

In the application note a stable protein sat near 0.05 and rose to ~0.1 at the
onset of thermal aggregation, so ~0.1 is a practical "elevated" threshold. An
index near 0 means the two angles agree (no forward-angle aggregate signature).

The index is a screening indicator: a high value flags a forward-weighted
large-species signal to corroborate with the distribution and orthogonal
methods, not a definitive aggregate quantification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from labassistant.metrics import calculate_tail_index, find_local_peaks
from labassistant.models import AngleSummary, Measurement

# Angle geometry (degrees).
FORWARD_TARGET_ANGLE = 12.8
BACKSCATTER_TARGET_ANGLE = 173.75
FORWARD_MAX_ANGLE = 90.0

# Aggregation Index thresholds, informed by the application note (0.05 stable,
# ~0.1 aggregation onset).
INDEX_WATCH = 0.05
INDEX_ELEVATED = 0.10
INDEX_HIGH = 0.30

# Correlogram baseline-noise thresholds for measurement confidence.
CONFIDENCE_HIGH_NOISE = 0.03
CONFIDENCE_MODERATE_NOISE = 0.06

# Corroboration thresholds.
FORWARD_TAIL_SUPPORT = 5.0          # forward large-particle tail (%) that supports aggregation
PEAK_SHIFT_SUPPORT_RATIO = 1.15     # forward/back primary-peak ratio that counts as a real shift
REPLICATE_CV_CONSISTENT = 0.15      # within-angle D50 coefficient of variation for "consistent"
DECAY_INTERCEPT_GOOD = 0.5          # mean correlogram intercept for good decay quality
DECAY_INTERCEPT_MODERATE = 0.2

# Interpretation categories.
CATEGORY_UNAVAILABLE = "Unavailable"
CATEGORY_LOW = "Low signal"
CATEGORY_WATCH = "Watch"
CATEGORY_ELEVATED = "Elevated"
CATEGORY_STRONG_CORROBORATED = "Strong signal, corroborated"
CATEGORY_STRONG_REPEAT = "Strong signal, repeat recommended"

# Checklist statuses.
SUPPORTS = "supports"
NEUTRAL = "neutral"
INSUFFICIENT = "insufficient"


@dataclass
class CorroborationCheck:
    label: str
    status: str  # SUPPORTS / NEUTRAL / INSUFFICIENT
    detail: str
    corroborating: bool = True  # counts toward the corroboration score
    independent_evidence: bool = False  # independent evidence *of aggregation* (not just confidence)


@dataclass
class DualAngleAggregation:
    available: bool = False
    aggregation_index: float | None = None
    forward: AngleSummary | None = None
    backward: AngleSummary | None = None
    forward_larger: bool = False
    elevated: bool = False
    level: str = "Unknown"
    category: str = CATEGORY_UNAVAILABLE
    forward_tail_index: float | None = None
    forward_secondary_peak_nm: float | None = None
    peak_shift_ratio: float | None = None
    correlogram_noise: float | None = None
    decay_quality: str | None = None
    replicate_consistency: str | None = None
    confidence: str = "Limited"
    checks: list[CorroborationCheck] = field(default_factory=list)
    corroboration_score: int = 0
    corroboration_max: int = 0
    flags: list[str] = field(default_factory=list)
    headline: str = ""
    recommendation: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "aggregation_index": self.aggregation_index,
            "forward_angle": self.forward.angle_degrees if self.forward else None,
            "backward_angle": self.backward.angle_degrees if self.backward else None,
            "forward_z_average": self.forward.z_average if self.forward else None,
            "backward_z_average": self.backward.z_average if self.backward else None,
            "forward_larger": self.forward_larger,
            "elevated": self.elevated,
            "level": self.level,
            "category": self.category,
            "forward_tail_index": self.forward_tail_index,
            "forward_secondary_peak_nm": self.forward_secondary_peak_nm,
            "peak_shift_ratio": self.peak_shift_ratio,
            "correlogram_noise": self.correlogram_noise,
            "decay_quality": self.decay_quality,
            "replicate_consistency": self.replicate_consistency,
            "confidence": self.confidence,
            "corroboration_score": self.corroboration_score,
            "corroboration_max": self.corroboration_max,
            "checks": [{"label": check.label, "status": check.status, "detail": check.detail} for check in self.checks],
            "flags": list(self.flags),
            "headline": self.headline,
            "recommendation": self.recommendation,
            "summary": self.summary,
        }


def identify_angle_pair(angle_summaries: list[AngleSummary]) -> tuple[AngleSummary | None, AngleSummary | None]:
    """Pick the forward (~12.8°) and backscatter (~173°) angle summaries.

    Chooses the summary nearest each target angle among those on the correct side
    of ``FORWARD_MAX_ANGLE``. Returns ``(None, None)`` if a valid pair is absent.
    """
    forwards = [summary for summary in angle_summaries if summary.angle_degrees is not None and summary.angle_degrees < FORWARD_MAX_ANGLE]
    backwards = [summary for summary in angle_summaries if summary.angle_degrees is not None and summary.angle_degrees >= FORWARD_MAX_ANGLE]
    if not forwards or not backwards:
        return None, None
    forward = min(forwards, key=lambda summary: abs(summary.angle_degrees - FORWARD_TARGET_ANGLE))
    backward = min(backwards, key=lambda summary: abs(summary.angle_degrees - BACKSCATTER_TARGET_ANGLE))
    return forward, backward


def calculate_aggregation_index(forward_z: float | None, backward_z: float | None) -> float | None:
    """Aggregation Index = Z_forward / Z_backscatter - 1."""
    if forward_z is None or backward_z is None or backward_z <= 0:
        return None
    return float(forward_z / backward_z - 1.0)


def classify_index(index: float | None) -> str:
    if index is None:
        return "Unknown"
    if index < INDEX_WATCH:
        return "None"
    if index < INDEX_ELEVATED:
        return "Low"
    if index < INDEX_HIGH:
        return "Moderate"
    return "High"


def assess_dual_angle_aggregation(measurement: Measurement) -> DualAngleAggregation:
    """Full dual-angle aggregation assessment for one measurement."""
    forward, backward = identify_angle_pair(measurement.angle_summaries)
    result = DualAngleAggregation(forward=forward, backward=backward)

    if forward is None or backward is None or forward.z_average is None or backward.z_average is None:
        result.summary = (
            "Dual-angle aggregation detection needs a forward (~12.8°) and a "
            "backscatter (~173°) Z-average. This measurement does not have both, "
            "so the Aggregation Index cannot be computed."
        )
        return result

    index = calculate_aggregation_index(forward.z_average, backward.z_average)
    result.aggregation_index = index
    result.available = index is not None
    result.forward_larger = index is not None and index > 0
    result.elevated = index is not None and index >= INDEX_ELEVATED
    result.level = classify_index(index)

    forward_distribution = measurement.distributions.get("angle_forward")
    if forward_distribution and forward_distribution.diameter_nm and forward_distribution.intensity:
        frame = pd.DataFrame({"d": forward_distribution.diameter_nm, "i": forward_distribution.intensity})
        result.forward_tail_index = calculate_tail_index(frame, "d", "i")
        peaks = find_local_peaks(frame, "d", "i")
        result.forward_secondary_peak_nm = peaks[1]["diameter"] if len(peaks) > 1 else None

    if forward.primary_peak_nm and backward.primary_peak_nm and backward.primary_peak_nm > 0:
        result.peak_shift_ratio = float(forward.primary_peak_nm / backward.primary_peak_nm)

    result.correlogram_noise = measurement.derived_metrics.correlogram_noise_score
    result.decay_quality = _decay_quality(measurement.correlogram)
    result.replicate_consistency = _replicate_consistency(measurement.provenance.get("angle_replicate_d50s"))
    result.confidence = _confidence(result.correlogram_noise, forward, backward, result.decay_quality, result.replicate_consistency)

    result.checks = _build_checklist(result, forward, backward)
    corroborating = [check for check in result.checks if check.corroborating]
    result.corroboration_max = sum(1 for check in corroborating if check.status != INSUFFICIENT)
    result.corroboration_score = sum(1 for check in corroborating if check.status == SUPPORTS)
    result.category = _category(result)

    result.flags = _flags(result)
    result.headline = _headline(result)
    result.recommendation = _recommendation(result)
    result.summary = _summary(result, forward, backward)
    return result


def _decay_quality(correlogram: list[dict]) -> str | None:
    """Rate correlogram decay quality from the mean intercept across replicates.

    A well-formed correlogram starts near its intercept (high g2-1) and decays
    smoothly; a low intercept means weak signal. Returns None with no correlogram.
    """
    if not correlogram:
        return None
    frame = pd.DataFrame(correlogram)
    if "correlation" not in frame or "replicate" not in frame:
        return None
    intercepts = []
    for _, rows in frame.groupby("replicate"):
        values = pd.to_numeric(rows["correlation"], errors="coerce").dropna()
        if not values.empty and values.max() > 0:
            intercepts.append(float(values.max()))
    if not intercepts:
        return None
    mean_intercept = sum(intercepts) / len(intercepts)
    if mean_intercept >= DECAY_INTERCEPT_GOOD:
        return "Good"
    if mean_intercept >= DECAY_INTERCEPT_MODERATE:
        return "Moderate"
    return "Poor"


def _replicate_consistency(replicate_d50s: dict | None) -> str | None:
    """Judge within-angle replicate agreement from per-angle D50 spread.

    "Consistent" when every angle with 2+ replicates has a D50 coefficient of
    variation at or below ``REPLICATE_CV_CONSISTENT``; "Variable" otherwise;
    None/"Insufficient" when there are not enough replicates to judge.
    """
    if not replicate_d50s:
        return None
    evaluable = False
    for values in replicate_d50s.values():
        numeric = [float(value) for value in values if value and value > 0]
        if len(numeric) < 2:
            continue
        evaluable = True
        mean = sum(numeric) / len(numeric)
        if mean <= 0:
            continue
        variance = sum((value - mean) ** 2 for value in numeric) / len(numeric)
        cv = (variance ** 0.5) / mean
        if cv > REPLICATE_CV_CONSISTENT:
            return "Variable"
    if not evaluable:
        return "Insufficient"
    return "Consistent"


def _confidence(
    noise: float | None,
    forward: AngleSummary,
    backward: AngleSummary,
    decay_quality: str | None,
    replicate_consistency: str | None,
) -> str:
    if noise is None:
        level = "Limited"
    elif noise < CONFIDENCE_HIGH_NOISE:
        level = "High"
    elif noise < CONFIDENCE_MODERATE_NOISE:
        level = "Moderate"
    else:
        level = "Low"

    order = ["Limited", "Low", "Moderate", "High"]

    def downgrade(current: str) -> str:
        index = order.index(current)
        return order[max(index - 1, 0)]

    replicates = min(forward.replicate_count or 0, backward.replicate_count or 0)
    if replicates and replicates < 2:
        level = downgrade(level)
    if decay_quality == "Poor":
        level = downgrade(level)
    if replicate_consistency == "Variable":
        level = downgrade(level)
    return level


def _build_checklist(result: DualAngleAggregation, forward: AngleSummary, backward: AngleSummary) -> list[CorroborationCheck]:
    index = result.aggregation_index
    checks: list[CorroborationCheck] = []

    # 1. Aggregation Index magnitude (the signal itself; not counted as corroboration).
    checks.append(
        CorroborationCheck(
            "Aggregation Index magnitude",
            SUPPORTS if index >= INDEX_ELEVATED else NEUTRAL,
            f"Index {index:.2f} (elevated ≥ {INDEX_ELEVATED:g}, strong ≥ {INDEX_HIGH:g}).",
            corroborating=False,
        )
    )

    # 2. Forward vs backscatter Z-average (the signal itself; not corroboration).
    fold = forward.z_average / backward.z_average if backward.z_average else None
    checks.append(
        CorroborationCheck(
            "Forward vs backscatter Z-average",
            SUPPORTS if fold and fold >= 1.10 else NEUTRAL,
            f"Forward {forward.z_average:.0f} nm vs backscatter {backward.z_average:.0f} nm"
            + (f" ({fold:.2f}×)." if fold else "."),
            corroborating=False,
        )
    )

    # 3. Forward intensity distribution evidence (independent evidence of aggregation).
    if result.forward_tail_index is None:
        checks.append(CorroborationCheck("Forward large-particle tail", INSUFFICIENT, "No forward-angle distribution to evaluate.", independent_evidence=True))
    elif result.forward_tail_index >= FORWARD_TAIL_SUPPORT:
        checks.append(CorroborationCheck("Forward large-particle tail", SUPPORTS, f"Forward tail {result.forward_tail_index:.1f}% (≥ {FORWARD_TAIL_SUPPORT:g}% supports).", independent_evidence=True))
    else:
        checks.append(CorroborationCheck("Forward large-particle tail", NEUTRAL, f"Forward tail {result.forward_tail_index:.1f}% (below {FORWARD_TAIL_SUPPORT:g}%).", independent_evidence=True))

    if result.forward_tail_index is None and result.forward_secondary_peak_nm is None:
        checks.append(CorroborationCheck("Forward secondary peak", INSUFFICIENT, "No forward-angle distribution to evaluate.", independent_evidence=True))
    elif result.forward_secondary_peak_nm is not None:
        checks.append(CorroborationCheck("Forward secondary peak", SUPPORTS, f"Secondary peak near {result.forward_secondary_peak_nm:.0f} nm at forward angle.", independent_evidence=True))
    else:
        checks.append(CorroborationCheck("Forward secondary peak", NEUTRAL, "Single forward-angle peak; no distinct secondary mode.", independent_evidence=True))

    if result.peak_shift_ratio is None:
        checks.append(CorroborationCheck("Forward vs back peak shift", INSUFFICIENT, "Per-angle primary peaks unavailable.", independent_evidence=True))
    elif result.peak_shift_ratio >= PEAK_SHIFT_SUPPORT_RATIO:
        checks.append(CorroborationCheck("Forward vs back peak shift", SUPPORTS, f"Forward peak {forward.primary_peak_nm:.0f} nm vs back {backward.primary_peak_nm:.0f} nm ({result.peak_shift_ratio:.2f}×).", independent_evidence=True))
    else:
        checks.append(CorroborationCheck("Forward vs back peak shift", NEUTRAL, f"Forward and back peaks are similar ({result.peak_shift_ratio:.2f}×).", independent_evidence=True))

    # 4. Correlogram confidence.
    if result.correlogram_noise is None:
        checks.append(CorroborationCheck("Correlogram baseline noise", INSUFFICIENT, "No correlogram supplied.", independent_evidence=False))
    elif result.correlogram_noise < CONFIDENCE_HIGH_NOISE:
        checks.append(CorroborationCheck("Correlogram baseline noise", SUPPORTS, f"Baseline noise {result.correlogram_noise:.3f} (< {CONFIDENCE_HIGH_NOISE:g}, clean).", independent_evidence=False))
    else:
        checks.append(CorroborationCheck("Correlogram baseline noise", NEUTRAL, f"Baseline noise {result.correlogram_noise:.3f} (≥ {CONFIDENCE_HIGH_NOISE:g}).", independent_evidence=False))

    if result.decay_quality is None:
        checks.append(CorroborationCheck("Correlogram decay quality", INSUFFICIENT, "No correlogram supplied.", independent_evidence=False))
    elif result.decay_quality == "Good":
        checks.append(CorroborationCheck("Correlogram decay quality", SUPPORTS, "Strong intercept and clean decay.", independent_evidence=False))
    else:
        checks.append(CorroborationCheck("Correlogram decay quality", NEUTRAL, f"{result.decay_quality} decay quality (weaker intercept).", independent_evidence=False))

    # 5. Replicate consistency across the two angles.
    if result.replicate_consistency in (None, "Insufficient"):
        checks.append(CorroborationCheck("Replicate consistency across angles", INSUFFICIENT, "Not enough replicates per angle to judge agreement.", independent_evidence=False))
    elif result.replicate_consistency == "Consistent":
        checks.append(CorroborationCheck("Replicate consistency across angles", SUPPORTS, "Forward and back replicates each agree internally.", independent_evidence=False))
    else:
        checks.append(CorroborationCheck("Replicate consistency across angles", NEUTRAL, "Replicate sizes vary within an angle.", independent_evidence=False))

    return checks


def _category(result: DualAngleAggregation) -> str:
    index = result.aggregation_index
    if index is None:
        return CATEGORY_UNAVAILABLE
    if index < INDEX_WATCH:
        return CATEGORY_LOW
    if index < INDEX_ELEVATED:
        return CATEGORY_WATCH
    if index < INDEX_HIGH:
        return CATEGORY_ELEVATED

    # Strong band: distinguish corroborated vs repeat-recommended.
    independent_supports = sum(1 for check in result.checks if check.independent_evidence and check.status == SUPPORTS)
    confident = result.confidence in ("High", "Moderate")
    if confident and independent_supports >= 1:
        return CATEGORY_STRONG_CORROBORATED
    return CATEGORY_STRONG_REPEAT


def _headline(result: DualAngleAggregation) -> str:
    category = result.category
    if category in (CATEGORY_STRONG_CORROBORATED, CATEGORY_STRONG_REPEAT):
        return "Strong dual-angle aggregation signal — forward-angle large-species enrichment."
    if category == CATEGORY_ELEVATED:
        return "Elevated dual-angle signal — forward-angle large-species enrichment."
    if category == CATEGORY_WATCH:
        return "Mild forward-angle size excess — watch for aggregation onset."
    if category == CATEGORY_LOW:
        return "No dual-angle aggregation signal — forward and backscatter agree."
    return "Dual-angle aggregation could not be assessed."


def _recommendation(result: DualAngleAggregation) -> str:
    category = result.category
    if category == CATEGORY_STRONG_CORROBORATED:
        return (
            "Requires corroboration. Multiple dual-angle lines agree, but this is not proof of "
            "aggregation: recommend review and orthogonal confirmation (e.g. SEC-MALS)."
        )
    if category == CATEGORY_STRONG_REPEAT:
        return (
            "Requires corroboration. Signal is strong but measurement confidence or independent "
            "evidence is limited: recommend repeat measurement and orthogonal confirmation."
        )
    if category == CATEGORY_ELEVATED:
        return "Requires corroboration. Treat as a screening signal: recommend review and repeat."
    if category == CATEGORY_WATCH:
        return "Monitor. Mild excess only; no action beyond routine review."
    if category == CATEGORY_LOW:
        return "No corroboration needed. The two angles agree."
    return ""


def _flags(result: DualAngleAggregation) -> list[str]:
    flags = []
    if result.forward_larger:
        flags.append("Forward scatter shows larger apparent size than backscatter")
    if result.elevated:
        flags.append(f"Elevated aggregation index ({result.aggregation_index:.2f})")
    if result.forward_tail_index is not None and result.forward_tail_index >= 5:
        flags.append(f"Large-particle tail at forward angle ({result.forward_tail_index:.1f}%)")
    if result.forward_secondary_peak_nm is not None:
        flags.append(f"Secondary peak at forward angle (~{result.forward_secondary_peak_nm:.0f} nm)")
    return flags


def _summary(result: DualAngleAggregation, forward: AngleSummary, backward: AngleSummary) -> str:
    index = result.aggregation_index
    forward_angle = f"{forward.angle_degrees:g}°" if forward.angle_degrees is not None else "forward"
    backward_angle = f"{backward.angle_degrees:g}°" if backward.angle_degrees is not None else "backscatter"

    parts = [
        f"Aggregation Index = Z({forward_angle}) / Z({backward_angle}) - 1 = {index:.2f} "
        f"({forward.z_average:.0f} nm vs {backward.z_average:.0f} nm)."
    ]

    if index >= INDEX_ELEVATED:
        parts.append(
            "Forward scatter weights large species much more heavily than backscatter, so an index "
            "this high points to forward-angle large-species enrichment. This is a screening signal, "
            "not proof of aggregation; corroborate with the distribution evidence and an orthogonal method."
        )
    elif index >= INDEX_WATCH:
        parts.append(
            "Forward scatter reads modestly larger than backscatter — a mild forward-angle "
            "size excess worth watching for the onset of aggregation."
        )
    elif index > 0:
        parts.append("Forward and backscatter are close, indicating little forward-angle aggregate signature.")
    else:
        parts.append("Forward scatter is not larger than backscatter, so there is no forward-angle aggregate signature.")

    parts.append("Reference baseline from Malvern AN101104/AN140527: ~0.05 stable, ~0.1 at aggregation onset.")
    return " ".join(parts)
