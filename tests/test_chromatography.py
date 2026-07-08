from labassistant.chromatography import (
    mass_balance_hypotheses,
    observations_from_chromatography_measurement,
    observations_from_mass_balance_assessment,
)
from labassistant.models import ChromatographyMeasurement, ChromatographyPeak, MassBalanceAssessment, Observation


def test_chromatography_measurement_generates_peak_and_run_observations():
    measurement = ChromatographyMeasurement(
        sample_name="Stress T1",
        injection_id="inj-1",
        peaks=[
            ChromatographyPeak(peak_id="unk-1", role="unknown", area_percent=1.4),
            ChromatographyPeak(peak_id="parent", role="parent", tailing_factor=2.1),
            ChromatographyPeak(peak_id="imp-1", role="known_impurity", coelution_suspected=True),
        ],
        replicate_rsd_percent=12.0,
        recovery_percent=78.0,
        baseline_status="drifting",
    )

    observations = observations_from_chromatography_measurement(measurement)
    labels = [observation.label for observation in observations]

    assert "Unknown peak appeared" in labels
    assert "Peak tailing increased" in labels
    assert "Co-elution suspected" in labels
    assert "Baseline changed" in labels
    assert "Replicate %RSD elevated" in labels
    assert "Recovery control failed" in labels


def test_mass_balance_assessment_generates_observations_and_hypotheses():
    assessment = MassBalanceAssessment(
        sample_name="Stress T2",
        parent_change_percent=-14.0,
        known_impurity_change_percent=4.0,
        unknown_area_percent=1.2,
        total_area_change_percent=-9.0,
        recovery_percent=80.0,
        replicate_rsd_percent=11.0,
    )

    observations = observations_from_mass_balance_assessment(assessment)
    hypotheses = mass_balance_hypotheses(observations)

    labels = [observation.label for observation in observations]
    assert labels == [
        "Parent peak decreased",
        "Known impurity increased",
        "Unknown peak appeared",
        "Total area decreased",
        "Replicate %RSD elevated",
        "Recovery control failed",
    ]
    assert "Degradation into detected impurities" in hypotheses
    assert "Incomplete recovery" in hypotheses


def test_dls_aggregation_plus_chromatography_loss_suggests_insoluble_missing_mass():
    chromatography_observations = observations_from_mass_balance_assessment(
        MassBalanceAssessment(
            sample_name="Stress T3",
            total_area_change_percent=-12.0,
            recovery_percent=75.0,
        )
    )
    dls_observations = [
        Observation(
            label="Forward scatter increased",
            category="particle_quality",
            evidence="DLS dual-angle aggregation signal.",
            sample_name="Stress T3",
        )
    ]

    hypotheses = mass_balance_hypotheses(chromatography_observations, dls_observations=dls_observations)

    assert "Missing mass may be associated with insoluble or aggregated material" in hypotheses
