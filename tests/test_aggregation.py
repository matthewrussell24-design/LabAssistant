from pytest import approx

from labassistant.aggregation import (
    CATEGORY_ELEVATED,
    CATEGORY_LOW,
    CATEGORY_STRONG_CORROBORATED,
    CATEGORY_STRONG_REPEAT,
    CATEGORY_WATCH,
    INDEX_ELEVATED,
    assess_dual_angle_aggregation,
    calculate_aggregation_index,
    classify_index,
    identify_angle_pair,
)
from labassistant.models import (
    AngleSummary,
    DerivedMetrics,
    DistributionData,
    Measurement,
    MeasurementMetadata,
)


def _good_correlogram() -> list[dict]:
    # Two replicates, high intercept (~0.9) decaying to baseline -> "Good" decay quality.
    rows = []
    for replicate in (1.0, 2.0):
        for time, corr in [(0.1, 0.9), (1.0, 0.6), (10.0, 0.2), (100.0, 0.0)]:
            rows.append({"delay_time": time, "correlation": corr, "replicate": replicate})
    return rows


def _dual_angle_measurement(
    forward_z: float,
    backward_z: float,
    forward_dist=None,
    forward_peak: float | None = None,
    backward_peak: float | None = None,
    noise: float | None = 0.02,
    correlogram=None,
    replicate_d50s=None,
) -> Measurement:
    distributions = {}
    if forward_dist is not None:
        distributions["angle_forward"] = forward_dist
    provenance = {}
    if replicate_d50s is not None:
        provenance["angle_replicate_d50s"] = replicate_d50s
    return Measurement(
        metadata=MeasurementMetadata(sample_name="Lot 1"),
        derived_metrics=DerivedMetrics(correlogram_noise_score=noise),
        angle_summaries=[
            AngleSummary(label="Forward 12.78°", angle_degrees=12.78, position="forward", z_average=forward_z, primary_peak_nm=forward_peak, replicate_count=9),
            AngleSummary(label="Back 174.7°", angle_degrees=174.7, position="back", z_average=backward_z, primary_peak_nm=backward_peak, replicate_count=9),
        ],
        distributions=distributions,
        correlogram=correlogram or [],
        provenance=provenance,
    )


def test_calculate_aggregation_index_matches_definition():
    assert calculate_aggregation_index(453.0, 265.0) == approx(453.0 / 265.0 - 1.0)
    assert calculate_aggregation_index(100.0, 100.0) == 0.0
    assert calculate_aggregation_index(None, 265.0) is None
    assert calculate_aggregation_index(453.0, 0.0) is None


def test_identify_angle_pair_picks_forward_and_backscatter():
    summaries = [
        AngleSummary(label="Back 174.7°", angle_degrees=174.7, position="back", z_average=265.0),
        AngleSummary(label="Forward 12.78°", angle_degrees=12.78, position="forward", z_average=453.0),
    ]
    forward, backward = identify_angle_pair(summaries)
    assert forward.angle_degrees == 12.78
    assert backward.angle_degrees == 174.7


def test_identify_angle_pair_requires_both_sides():
    only_back = [AngleSummary(label="Back 173°", angle_degrees=173.0, z_average=265.0)]
    assert identify_angle_pair(only_back) == (None, None)


def test_classify_index_thresholds():
    assert classify_index(None) == "Unknown"
    assert classify_index(0.02) == "None"
    assert classify_index(0.07) == "Low"
    assert classify_index(0.2) == "Moderate"
    assert classify_index(0.7) == "High"


def test_assess_flags_elevated_aggregation_and_forward_excess():
    measurement = _dual_angle_measurement(453.0, 265.0)
    result = assess_dual_angle_aggregation(measurement)

    assert result.available is True
    assert result.aggregation_index == approx(0.709, abs=0.005)
    assert result.forward_larger is True
    assert result.elevated is True
    assert result.level == "High"
    assert result.aggregation_index >= INDEX_ELEVATED
    assert any("Forward scatter shows larger" in flag for flag in result.flags)
    assert any("Elevated aggregation index" in flag for flag in result.flags)
    assert result.confidence == "High"  # low correlogram noise


def test_assess_reports_no_signature_when_angles_agree():
    measurement = _dual_angle_measurement(268.0, 265.0)
    result = assess_dual_angle_aggregation(measurement)

    assert result.available is True
    assert result.elevated is False
    assert result.level == "None"


def test_assess_uses_forward_distribution_for_tail_and_secondary_peak():
    forward_dist = DistributionData(
        diameter_nm=[100.0, 300.0, 500.0, 1500.0, 3000.0],
        intensity=[10.0, 100.0, 30.0, 40.0, 20.0],
    )
    measurement = _dual_angle_measurement(453.0, 265.0, forward_dist=forward_dist)
    result = assess_dual_angle_aggregation(measurement)

    assert result.forward_tail_index is not None and result.forward_tail_index > 0
    assert any("Large-particle tail" in flag for flag in result.flags)


def test_assess_unavailable_without_dual_angle():
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name="Single"),
        angle_summaries=[AngleSummary(label="Back 173°", angle_degrees=173.0, z_average=265.0)],
    )
    result = assess_dual_angle_aggregation(measurement)

    assert result.available is False
    assert result.aggregation_index is None
    assert "needs a forward" in result.summary


def test_categories_track_index_bands():
    assert assess_dual_angle_aggregation(_dual_angle_measurement(268.0, 265.0)).category == CATEGORY_LOW
    assert assess_dual_angle_aggregation(_dual_angle_measurement(285.0, 265.0)).category == CATEGORY_WATCH  # index ~0.075
    assert assess_dual_angle_aggregation(_dual_angle_measurement(320.0, 265.0)).category == CATEGORY_ELEVATED  # index ~0.21


def test_strong_signal_corroborated_when_evidence_and_confidence_agree():
    result = assess_dual_angle_aggregation(
        _dual_angle_measurement(
            453.0,
            265.0,
            forward_peak=420.0,
            backward_peak=267.0,  # 1.57x peak shift -> independent evidence
            noise=0.015,          # clean baseline
            correlogram=_good_correlogram(),
            replicate_d50s={"forward": [415.0, 420.0, 425.0], "back": [265.0, 267.0, 266.0]},
        )
    )

    assert result.category == CATEGORY_STRONG_CORROBORATED
    assert result.confidence == "High"
    assert result.decay_quality == "Good"
    assert result.replicate_consistency == "Consistent"
    assert result.corroboration_score >= 3
    assert "Requires corroboration" in result.recommendation
    assert "large-species enrichment" in result.headline
    # Never phrases the index as proof.
    assert "proof" not in result.summary.lower() or "not proof" in result.summary.lower()


def test_strong_signal_repeat_recommended_when_confidence_and_evidence_are_thin():
    result = assess_dual_angle_aggregation(
        _dual_angle_measurement(
            453.0,
            265.0,
            forward_peak=None,   # no peak shift evidence
            backward_peak=None,
            noise=0.12,          # noisy baseline -> Low confidence
            correlogram=None,
            replicate_d50s={"forward": [300.0, 500.0], "back": [200.0, 340.0]},  # variable
        )
    )

    assert result.category == CATEGORY_STRONG_REPEAT
    assert "repeat" in result.recommendation.lower()


def test_checklist_covers_all_five_evidence_areas():
    result = assess_dual_angle_aggregation(_dual_angle_measurement(453.0, 265.0, forward_peak=420.0, backward_peak=267.0))
    labels = [check.label for check in result.checks]

    for expected in [
        "Aggregation Index magnitude",
        "Forward vs backscatter Z-average",
        "Forward large-particle tail",
        "Forward secondary peak",
        "Forward vs back peak shift",
        "Correlogram baseline noise",
        "Correlogram decay quality",
        "Replicate consistency across angles",
    ]:
        assert expected in labels
    # Corroboration score counts only supporting corroborating checks.
    assert result.corroboration_score <= result.corroboration_max
