import pandas as pd

from labassistant.chromatography import (
    mass_balance_hypotheses,
    observations_from_mass_balance_assessment,
)
from labassistant.filtration import observations_from_filtration_measurement
from labassistant.investigator import investigate
from labassistant.models import (
    Experiment,
    FiltrationMeasurement,
    MassBalanceAssessment,
    Measurement,
    MeasurementMetadata,
)
from labassistant.observations import observations_from_sample
from labassistant.view_models import ParsedSample


def test_cross_technique_investigation_links_missing_mass_particles_and_filtration():
    sample_name = "Stress T3"
    dls_sample = ParsedSample(
        name=sample_name,
        file_name="dls.xlsx",
        data=pd.DataFrame(),
        metadata={},
        metrics={"Aggregation Index": 0.71, "Correlogram Noise": None},
        warnings=["Dual-angle aggregation"],
        source_text="",
        measurement=Measurement(
            metadata=MeasurementMetadata(sample_name=sample_name),
            provenance={
                "dual_angle_aggregation": {
                    "category": "Strong signal, corroborated",
                    "confidence": "High",
                    "corroboration_score": 4,
                    "corroboration_max": 6,
                    "recommendation": "Confirm with SEC-MALS.",
                }
            },
        ),
    )
    dls_observations = observations_from_sample(dls_sample)
    chromatography_observations = observations_from_mass_balance_assessment(
        MassBalanceAssessment(
            sample_name=sample_name,
            total_area_change_percent=-18.0,
            recovery_percent=72.0,
        )
    )
    filtration_observations = observations_from_filtration_measurement(
        FiltrationMeasurement(
            sample_name=sample_name,
            difficulty_score=4,
            clogging_observed=True,
            source_file="filtration.csv",
        )
    )
    observations = dls_observations + chromatography_observations + filtration_observations
    hypotheses = mass_balance_hypotheses(
        chromatography_observations,
        dls_observations=dls_observations,
        filtration_observations=filtration_observations,
    )
    experiment = Experiment(
        experiment_id="cross-technique-1",
        label="Stress and filtration investigation",
        technique="Cross-technique",
        observations=observations,
        metadata={"hypotheses": hypotheses},
    )

    report = investigate(experiment)

    assert report.is_interpretable is True
    assert report.is_complete is True
    assert report.observation_counts == {"review": 5}
    assert {observation.source_type for observation in observations} == {
        "dls_dual_angle",
        "mass_balance_assessment",
        "filtration_follow_up",
    }
    assert all(observation.sample_name == sample_name for observation in observations)
    assert (
        "Missing mass, particle growth, and filtration difficulty may share an insoluble or aggregated-material association"
        in hypotheses
    )
    assert not any("caused" in hypothesis.lower() for hypothesis in hypotheses)
    assert any("Forward scatter increased" in highlight for highlight in report.highlights)
    assert any("Filter clogging observed" in highlight for highlight in report.highlights)
