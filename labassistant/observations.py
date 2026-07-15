from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from labassistant.models import Observation
from labassistant.quality import STATUS_REVIEW, STATUS_WATCH
from labassistant.dls_evidence import DLSSampleEvidence, sample_status

ParsedSample = DLSSampleEvidence


def observations_from_samples(samples: list[ParsedSample]) -> list[Observation]:
    observations: list[Observation] = []
    for sample in samples:
        observations.extend(observations_from_sample(sample))
    return observations


def observations_from_sample(sample: ParsedSample) -> list[Observation]:
    observations: list[Observation] = []
    warnings = set(sample.warnings)

    for warning in sample.warnings:
        observation = _observation_from_warning(sample, warning)
        if observation is not None:
            observations.append(observation)

    correlogram_noise = _metric(sample, "Correlogram Noise")
    if correlogram_noise is not None:
        if correlogram_noise <= 0.02:
            observations.append(
                Observation(
                    label="Stable correlogram baseline",
                    category="signal_quality",
                    sample_name=sample.name,
                    severity="normal",
                    confidence="medium",
                    evidence=f"Correlogram baseline noise {correlogram_noise:.3f}.",
                    source_type="dls_correlogram",
                )
            )
        elif correlogram_noise >= 0.08:
            observations.append(
                Observation(
                    label="Noisy correlogram baseline",
                    category="signal_quality",
                    sample_name=sample.name,
                    severity="watch",
                    confidence="medium",
                    evidence=f"Correlogram baseline noise {correlogram_noise:.3f}.",
                    source_type="dls_correlogram",
                    recommendation="Repeat or review the correlogram before trusting fine differences.",
                )
            )

    if not warnings:
        observations.append(
            Observation(
                label="No DLS review signal detected",
                category="quality_assessment",
                sample_name=sample.name,
                severity="normal",
                confidence="medium",
                evidence="No active DLS warning thresholds were crossed.",
                source_type="dls_analysis",
                recommendation="Use as a provisional reference if other experiment context agrees.",
            )
        )

    return observations


def observation_table(observations: list[Observation]) -> pd.DataFrame:
    return pd.DataFrame([asdict(observation) for observation in observations])


def build_experiment_brief_from_observations(observations: list[Observation], sample_count: int) -> dict[str, list[str]]:
    review = [observation for observation in observations if observation.severity == "review"]
    watch = [observation for observation in observations if observation.severity == "watch"]
    normal = [observation for observation in observations if observation.severity == "normal"]
    concerning = review or watch

    if concerning:
        top = concerning[:3]
        what_happened = [
            f"{len(concerning)} observation(s) need attention across {sample_count} sample(s): {_observation_list(top)}."
        ]
    else:
        what_happened = [
            f"No observation crossed the current review rules across {sample_count} sample(s)."
        ]

    if review:
        trustworthy = [
            "Evidence is not yet fully trustworthy for release decisions; review-level observations require confirmation."
        ]
    elif watch:
        trustworthy = [
            "Evidence is usable as screening information, but watch-level observations should be checked before drawing strong conclusions."
        ]
    else:
        trustworthy = [
            "Evidence is internally consistent by the current DLS rules."
        ]
    if any(observation.category == "signal_quality" and observation.severity == "watch" for observation in observations):
        trustworthy.append("Signal-quality observations reduce confidence in subtle differences.")
    elif any(observation.label == "Stable correlogram baseline" for observation in observations):
        trustworthy.append("Correlogram baseline observations support measurement trustworthiness.")

    why = _why_might_it_have_happened(concerning)
    next_steps = _next_steps(concerning, normal)

    return {
        "What happened?": what_happened,
        "Is the evidence trustworthy?": trustworthy,
        "Why might it have happened?": why,
        "What should be investigated next?": next_steps,
    }


def _observation_from_warning(sample: ParsedSample, warning: str) -> Observation | None:
    status = sample_status(sample)
    severity = "review" if status == STATUS_REVIEW else "watch" if status == STATUS_WATCH else "info"
    source_id = sample.file_name or sample.name

    if warning in {"High PDI", "Moderate PDI"}:
        pdi = _metric(sample, "PDI")
        return Observation(
            label="High variability",
            category="reproducibility",
            sample_name=sample.name,
            severity=severity,
            confidence="high" if pdi is not None else "medium",
            evidence=f"PDI {_format_number(pdi, digits=3)}." if pdi is not None else warning,
            source_type="dls_summary",
            source_id=source_id,
            recommendation="Check replicate agreement and repeat if this sample drives the experiment conclusion.",
        )

    if warning == "Secondary peak":
        secondary = _metric(sample, "Secondary Peak")
        return Observation(
            label="Secondary particle population detected",
            category="particle_quality",
            sample_name=sample.name,
            severity=severity,
            confidence="medium",
            evidence=f"Secondary peak at {_format_number(secondary, 'nm')}." if secondary is not None else warning,
            source_type="dls_distribution",
            source_id=source_id,
            recommendation="Inspect the distribution and consider orthogonal particle or purity analysis.",
        )

    if warning == "Large-particle tail":
        tail = _metric(sample, "Tail Index")
        return Observation(
            label="Large-particle tail detected",
            category="particle_quality",
            sample_name=sample.name,
            severity=severity,
            confidence="medium",
            evidence=f"Tail index {_format_number(tail, '%')}." if tail is not None else warning,
            source_type="dls_distribution",
            source_id=source_id,
            recommendation="Check for aggregate or oversized material and compare against prior experiments.",
        )

    if warning == "Broad distribution":
        width = _metric(sample, "Width Ratio")
        return Observation(
            label="Particle-size distribution broadened",
            category="particle_quality",
            sample_name=sample.name,
            severity=severity,
            confidence="medium",
            evidence=f"D90/D10 width ratio {_format_number(width)}." if width is not None else warning,
            source_type="dls_distribution",
            source_id=source_id,
            recommendation="Review sample preparation and compare with orthogonal sizing if available.",
        )

    if warning == "Dual-angle aggregation":
        assessment = sample.measurement.provenance.get("dual_angle_aggregation", {})
        index = _metric(sample, "Aggregation Index")
        category = assessment.get("category")
        evidence_parts = []
        if category:
            evidence_parts.append(str(category))
        if index is not None:
            evidence_parts.append(f"Aggregation Index {_format_number(index)}")
        if assessment.get("corroboration_score") is not None:
            evidence_parts.append(f"corroboration {assessment['corroboration_score']}/{assessment.get('corroboration_max')}")
        return Observation(
            label="Forward scatter increased",
            category="particle_quality",
            sample_name=sample.name,
            severity="review",
            confidence=str(assessment.get("confidence") or "medium").lower(),
            evidence=", ".join(evidence_parts) if evidence_parts else "Dual-angle aggregation signal.",
            source_type="dls_dual_angle",
            source_id=source_id,
            recommendation=str(assessment.get("recommendation") or "Review and confirm with an orthogonal method."),
        )

    if warning == "Distribution columns need review":
        return Observation(
            label="Distribution parsing uncertain",
            category="data_quality",
            sample_name=sample.name,
            severity="watch",
            confidence="high",
            evidence="The app could not confidently identify distribution columns.",
            source_type="dls_parser",
            source_id=source_id,
            recommendation="Review the source export before relying on chart-derived findings.",
        )

    return Observation(
        label=warning,
        category="dls_finding",
        sample_name=sample.name,
        severity=severity,
        confidence="medium",
        evidence=warning,
        source_type="dls_analysis",
        source_id=source_id,
    )


def _why_might_it_have_happened(observations: list[Observation]) -> list[str]:
    if not observations:
        return ["No concerning observation was detected, so no failure hypothesis is suggested by the current DLS rules."]

    categories = {observation.category for observation in observations}
    reasons = []
    if "particle_quality" in categories:
        reasons.append("Particle-quality observations may reflect aggregation, broadening, or multiple particle populations.")
    if "reproducibility" in categories:
        reasons.append("Reproducibility observations may reflect sample heterogeneity, preparation variability, or unstable measurement conditions.")
    if "signal_quality" in categories or "data_quality" in categories:
        reasons.append("Data-quality observations may reflect instrument signal quality, export parsing, or run setup rather than true sample behavior.")
    return reasons or ["The current observations are nonspecific; compare against history or orthogonal assays before assigning cause."]


def _next_steps(concerning: list[Observation], normal: list[Observation]) -> list[str]:
    if concerning:
        recommendations = []
        seen = set()
        for observation in concerning:
            if observation.recommendation and observation.recommendation not in seen:
                recommendations.append(f"{observation.sample_name}: {observation.recommendation}" if observation.sample_name else observation.recommendation)
                seen.add(observation.recommendation)
            if len(recommendations) == 3:
                break
        return recommendations or ["Review the highest-severity observation first and repeat or confirm before acting."]

    if normal:
        return ["Use the current DLS result as provisional evidence and compare it against historical experiments or orthogonal techniques when available."]
    return ["Import measurements or add notes to generate experiment observations."]


def _observation_list(observations: list[Observation]) -> str:
    return "; ".join(
        f"{observation.sample_name}: {observation.label}" if observation.sample_name else observation.label
        for observation in observations
    )


def _metric(sample: ParsedSample, metric: str) -> float | None:
    value = sample.metrics.get(metric)
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: Any, unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "not found"
    formatted = f"{float(value):,.{digits}f}".rstrip("0").rstrip(".")
    return f"{formatted} {unit}".strip()
