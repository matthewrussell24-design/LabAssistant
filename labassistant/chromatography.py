from __future__ import annotations

from labassistant.models import ChromatographyMeasurement, ChromatographyPeak, MassBalanceAssessment, Observation


PARENT_DECREASE_THRESHOLD_PERCENT = -5.0
TOTAL_AREA_DECREASE_THRESHOLD_PERCENT = -5.0
IMPURITY_INCREASE_THRESHOLD_PERCENT = 2.0
UNKNOWN_AREA_THRESHOLD_PERCENT = 1.0
REPLICATE_RSD_THRESHOLD_PERCENT = 10.0
RECOVERY_LOW_THRESHOLD_PERCENT = 85.0
TAILING_FACTOR_THRESHOLD = 1.8
RETENTION_TIME_SHIFT_THRESHOLD_MIN = 0.2


def observations_from_chromatography_measurement(measurement: ChromatographyMeasurement) -> list[Observation]:
    """Generate normalized observations from chromatographic peak metadata.

    This is intentionally not a parser. It assumes a future ingestion adapter has
    already populated peaks and run-level fields.
    """
    observations: list[Observation] = []

    for peak in measurement.peaks:
        if peak.role == "unknown" and (peak.area_percent or 0) >= UNKNOWN_AREA_THRESHOLD_PERCENT:
            observations.append(
                _peak_observation(
                    measurement,
                    peak,
                    label="Unknown peak appeared",
                    category="chromatography_mass_balance",
                    severity="watch",
                    evidence=f"Unknown peak {peak.peak_id} represents {peak.area_percent:.2f}% area.",
                    recommendation="Identify the unknown peak or compare against stressed and blank controls.",
                )
            )
        if peak.coelution_suspected:
            observations.append(
                _peak_observation(
                    measurement,
                    peak,
                    label="Co-elution suspected",
                    category="chromatography_quality",
                    severity="watch",
                    evidence=f"Peak {peak.peak_id} is marked as potentially co-eluting.",
                    recommendation="Review integration and method resolution before assigning mass balance.",
                )
            )
        if peak.tailing_factor is not None and peak.tailing_factor >= TAILING_FACTOR_THRESHOLD:
            observations.append(
                _peak_observation(
                    measurement,
                    peak,
                    label="Peak tailing increased",
                    category="chromatography_quality",
                    severity="watch",
                    evidence=f"Peak {peak.peak_id} tailing factor is {peak.tailing_factor:.2f}.",
                    recommendation="Check column/method performance and integration boundaries.",
                )
            )
        if peak.width_seconds is not None and peak.metadata.get("reference_width_seconds"):
            reference_width = float(peak.metadata["reference_width_seconds"])
            if reference_width > 0 and peak.width_seconds / reference_width >= 1.5:
                observations.append(
                    _peak_observation(
                        measurement,
                        peak,
                        label="Peak broadened",
                        category="chromatography_quality",
                        severity="watch",
                        evidence=f"Peak {peak.peak_id} width increased from {reference_width:.1f}s to {peak.width_seconds:.1f}s.",
                        recommendation="Check method stability, sample matrix, or co-elution.",
                    )
                )

    if measurement.baseline_status and measurement.baseline_status.lower() not in {"stable", "normal", "ok"}:
        observations.append(
            Observation(
                label="Baseline changed",
                category="chromatography_quality",
                sample_name=measurement.sample_name,
                severity="watch",
                confidence="medium",
                evidence=f"Baseline status: {measurement.baseline_status}.",
                source_type="chromatography_measurement",
                source_id=measurement.injection_id,
                recommendation="Review blank/control injections and baseline integration.",
            )
        )

    if measurement.replicate_rsd_percent is not None and measurement.replicate_rsd_percent >= REPLICATE_RSD_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Replicate %RSD elevated",
                category="reproducibility",
                sample_name=measurement.sample_name,
                severity="watch",
                confidence="high",
                evidence=f"Replicate RSD is {measurement.replicate_rsd_percent:.1f}%.",
                source_type="chromatography_replicates",
                source_id=measurement.injection_id,
                recommendation="Review injection reproducibility and repeat if the mass-balance conclusion depends on this result.",
            )
        )

    if measurement.recovery_percent is not None and measurement.recovery_percent < RECOVERY_LOW_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Recovery control failed",
                category="mass_balance",
                sample_name=measurement.sample_name,
                severity="review",
                confidence="high",
                evidence=f"Recovery is {measurement.recovery_percent:.1f}%.",
                source_type="chromatography_recovery",
                source_id=measurement.injection_id,
                recommendation="Investigate recovery, preparation loss, adsorption, precipitation, or detector response.",
            )
        )

    return observations


def observations_from_mass_balance_assessment(assessment: MassBalanceAssessment) -> list[Observation]:
    observations = list(assessment.observations)

    if assessment.parent_change_percent is not None and assessment.parent_change_percent <= PARENT_DECREASE_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Parent peak decreased",
                category="mass_balance",
                sample_name=assessment.sample_name,
                severity="watch",
                confidence="medium",
                evidence=f"Parent area changed by {assessment.parent_change_percent:.1f}%.",
                source_type="mass_balance_assessment",
                recommendation="Compare parent loss against impurity growth, total area, and recovery controls.",
            )
        )

    if assessment.known_impurity_change_percent is not None and assessment.known_impurity_change_percent >= IMPURITY_INCREASE_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Known impurity increased",
                category="mass_balance",
                sample_name=assessment.sample_name,
                severity="watch",
                confidence="medium",
                evidence=f"Known impurity area changed by {assessment.known_impurity_change_percent:.1f}%.",
                source_type="mass_balance_assessment",
                recommendation="Check whether impurity growth accounts for parent loss.",
            )
        )

    if assessment.unknown_area_percent is not None and assessment.unknown_area_percent >= UNKNOWN_AREA_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Unknown peak appeared",
                category="mass_balance",
                sample_name=assessment.sample_name,
                severity="watch",
                confidence="medium",
                evidence=f"Unknown peak area is {assessment.unknown_area_percent:.2f}%.",
                source_type="mass_balance_assessment",
                recommendation="Identify unknown peaks and assess whether they explain missing mass.",
            )
        )

    if assessment.total_area_change_percent is not None and assessment.total_area_change_percent <= TOTAL_AREA_DECREASE_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Total area decreased",
                category="mass_balance",
                sample_name=assessment.sample_name,
                severity="review",
                confidence="medium",
                evidence=f"Total chromatographic area changed by {assessment.total_area_change_percent:.1f}%.",
                source_type="mass_balance_assessment",
                recommendation="Investigate recovery, detector response, sample prep loss, precipitation, or integration choices.",
            )
        )

    if assessment.retention_time_shift_min is not None and abs(assessment.retention_time_shift_min) >= RETENTION_TIME_SHIFT_THRESHOLD_MIN:
        observations.append(
            Observation(
                label="Retention time shifted",
                category="chromatography_quality",
                sample_name=assessment.sample_name,
                severity="watch",
                confidence="medium",
                evidence=f"Parent retention time shifted by {assessment.retention_time_shift_min:.2f} min.",
                source_type="mass_balance_assessment",
                recommendation="Check method stability, matrix effects, and system suitability.",
            )
        )

    if assessment.replicate_rsd_percent is not None and assessment.replicate_rsd_percent >= REPLICATE_RSD_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Replicate %RSD elevated",
                category="reproducibility",
                sample_name=assessment.sample_name,
                severity="watch",
                confidence="high",
                evidence=f"Replicate RSD is {assessment.replicate_rsd_percent:.1f}%.",
                source_type="mass_balance_assessment",
                recommendation="Repeat or review integration before interpreting mass-balance deltas.",
            )
        )

    if assessment.recovery_percent is not None and assessment.recovery_percent < RECOVERY_LOW_THRESHOLD_PERCENT:
        observations.append(
            Observation(
                label="Recovery control failed",
                category="mass_balance",
                sample_name=assessment.sample_name,
                severity="review",
                confidence="high",
                evidence=f"Recovery is {assessment.recovery_percent:.1f}%.",
                source_type="mass_balance_assessment",
                recommendation="Investigate recovery, preparation loss, adsorption, precipitation, or detector response.",
            )
        )

    return observations


def mass_balance_hypotheses(
    observations: list[Observation],
    *,
    dls_observations: list[Observation] | None = None,
    filtration_observations: list[Observation] | None = None,
) -> list[str]:
    labels = {observation.label for observation in observations}
    dls_labels = {observation.label for observation in dls_observations or []}
    filtration_labels = {
        observation.label for observation in filtration_observations or []
    }
    hypotheses: list[str] = []

    if "Parent peak decreased" in labels and "Known impurity increased" in labels:
        hypotheses.append("Degradation into detected impurities")
    if "Total area decreased" in labels and "Known impurity increased" not in labels:
        hypotheses.append("Degradation into non-detected species")
    if "Unknown peak appeared" in labels:
        hypotheses.append("Degradation into unknown chromatographic species")
    if "Co-elution suspected" in labels:
        hypotheses.append("Co-elution")
    if "Peak tailing increased" in labels or "Baseline changed" in labels or "Retention time shifted" in labels:
        hypotheses.append("Method instability or integration error")
    if "Recovery control failed" in labels:
        hypotheses.append("Incomplete recovery")
        hypotheses.append("Adsorption/sample prep loss")
    if "Replicate %RSD elevated" in labels:
        hypotheses.append("Injection, preparation, or integration reproducibility issue")
    if {"Total area decreased", "Recovery control failed"} & labels and dls_labels & {
        "Forward scatter increased",
        "Large-particle tail detected",
        "Particle-size distribution broadened",
    }:
        hypotheses.append("Missing mass may be associated with insoluble or aggregated material")
        if filtration_labels & {"Filtration difficulty elevated", "Filter clogging observed"}:
            hypotheses.append(
                "Missing mass, particle growth, and filtration difficulty may share an insoluble or aggregated-material association"
            )

    return list(dict.fromkeys(hypotheses))


def _peak_observation(
    measurement: ChromatographyMeasurement,
    peak: ChromatographyPeak,
    *,
    label: str,
    category: str,
    severity: str,
    evidence: str,
    recommendation: str,
) -> Observation:
    return Observation(
        label=label,
        category=category,
        sample_name=measurement.sample_name,
        severity=severity,
        confidence="medium",
        evidence=evidence,
        source_type=f"{measurement.technique.lower()}_peak",
        source_id=peak.peak_id,
        recommendation=recommendation,
    )
