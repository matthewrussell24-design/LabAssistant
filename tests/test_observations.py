import pandas as pd

from labassistant.models import Measurement, MeasurementFlag, MeasurementMetadata
from labassistant.observations import (
    build_experiment_brief_from_observations,
    observation_table,
    observations_from_sample,
)
from labassistant.view_models import ParsedSample


def make_sample(name: str, warnings: list[str], metrics: dict | None = None, provenance: dict | None = None) -> ParsedSample:
    base_metrics = {
        "Data Type": "Multi-file Measurement",
        "Z-Average": 100.0,
        "PDI": 0.12,
        "Secondary Peak": None,
        "Tail Index": 0.0,
        "Width Ratio": 3.0,
        "Aggregation Index": None,
        "Correlogram Noise": None,
    }
    base_metrics.update(metrics or {})
    return ParsedSample(
        name=name,
        file_name=f"{name}.xlsx",
        data=pd.DataFrame(),
        metadata={},
        metrics=base_metrics,
        warnings=warnings,
        source_text="",
        measurement=Measurement(
            metadata=MeasurementMetadata(sample_name=name),
            flags=[MeasurementFlag(label=warning) for warning in warnings],
            provenance=provenance or {},
        ),
    )


def test_dls_warnings_become_observations():
    sample = make_sample(
        "Lot 1",
        ["Moderate PDI", "Large-particle tail"],
        metrics={"PDI": 0.35, "Tail Index": 7.2},
    )

    observations = observations_from_sample(sample)

    labels = [observation.label for observation in observations]
    assert labels == ["High variability", "Large-particle tail detected"]
    assert observations[0].category == "reproducibility"
    assert observations[0].evidence == "PDI 0.35."
    assert observations[1].category == "particle_quality"
    assert observations[1].evidence == "Tail index 7.2 %."


def test_dual_angle_assessment_becomes_forward_scatter_observation():
    sample = make_sample(
        "Lot 2",
        ["Dual-angle aggregation"],
        metrics={"Aggregation Index": 0.71},
        provenance={
            "dual_angle_aggregation": {
                "category": "Strong signal, corroborated",
                "confidence": "High",
                "corroboration_score": 4,
                "corroboration_max": 6,
                "recommendation": "Confirm with SEC-MALS.",
            }
        },
    )

    observations = observations_from_sample(sample)

    assert len(observations) == 1
    observation = observations[0]
    assert observation.label == "Forward scatter increased"
    assert observation.severity == "review"
    assert observation.confidence == "high"
    assert "Aggregation Index 0.71" in observation.evidence
    assert observation.recommendation == "Confirm with SEC-MALS."


def test_experiment_brief_uses_observation_severity():
    clean = observations_from_sample(make_sample("Clean", []))
    flagged = observations_from_sample(make_sample("Flagged", ["High PDI"], metrics={"PDI": 0.62}))
    observations = clean + flagged

    brief = build_experiment_brief_from_observations(observations, sample_count=2)
    table = observation_table(observations)

    assert "Flagged: High variability" in brief["What happened?"][0]
    assert "not yet fully trustworthy" in brief["Is the evidence trustworthy?"][0]
    assert any("Reproducibility observations" in item for item in brief["Why might it have happened?"])
    assert "Observation" not in table.columns
    assert {"label", "category", "severity", "evidence"}.issubset(table.columns)
