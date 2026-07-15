import pandas as pd

from labassistant.interpretation import build_ai_summary, build_decision_brief, review_evidence
from labassistant.models import (
    DerivedMetrics,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    SummaryMetrics,
)
from labassistant.view_models import ParsedSample, build_metrics_table


def make_sample(name: str, pdi: float, warnings: list[str]) -> ParsedSample:
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name=name),
        summary_metrics=SummaryMetrics(z_average=100.0, pdi=pdi),
        derived_metrics=DerivedMetrics(
            primary_peak_nm=100.0,
            tail_index_percent=0.0,
            width_ratio=3.0,
            d10_nm=50.0,
            d50_nm=100.0,
            d90_nm=150.0,
        ),
        flags=[MeasurementFlag(label=warning) for warning in warnings],
        provenance={"data_type": "Distribution Curve"},
    )
    return ParsedSample(
        name=name,
        file_name=f"{name}.csv",
        data=pd.DataFrame(),
        metadata={},
        metrics={
            "Data Type": "Distribution Curve",
            "Z-Average": 100.0,
            "PDI": pdi,
            "Max Z-Average": None,
            "Max PDI": None,
            "Measurement Count": None,
            "Scattering Angles": None,
            "Primary Peak": 100.0,
            "Secondary Peak": None,
            "Count Rate": None,
            "Tail Index": 0.0,
            "Width Ratio": 3.0,
            "D10": 50.0,
            "D50": 100.0,
            "D90": 150.0,
            "Diameter Column": "Diameter",
            "Intensity Column": "Intensity",
            "Volume Column": None,
            "Number Column": None,
            "Preferred Distribution": "Intensity",
            "Z-Average Column": None,
            "PDI Column": None,
            "Scattering Angle Column": None,
            "Measurement Date": None,
        },
        warnings=warnings,
        source_text="",
        measurement=measurement,
    )


def test_decision_brief_and_summary_prioritize_flagged_sample():
    clean = make_sample("clean", 0.12, [])
    flagged = make_sample("flagged", 0.35, ["Moderate PDI"])
    samples = [clean, flagged]
    metrics = build_metrics_table(samples)

    decision = build_decision_brief(samples, metrics)
    summary = build_ai_summary(samples, metrics)

    assert review_evidence(flagged) == "PDI 0.35"
    assert decision["best"] == "clean (Normal)"
    assert decision["worst"] == "flagged (Watch)"
    assert decision["flagged"] == "1 of 2"
    assert "flagged: PDI 0.35" in summary["Samples Needing Review"]
