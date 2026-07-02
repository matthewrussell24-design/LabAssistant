from labassistant.models import (
    AngleSummary,
    DerivedMetrics,
    DistributionData,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    SummaryMetrics,
)


def test_measurement_uses_independent_defaults():
    first = Measurement(metadata=MeasurementMetadata(sample_name="A"))
    second = Measurement(metadata=MeasurementMetadata(sample_name="B"))

    first.add_flag("High PDI")
    first.distributions["intensity"] = DistributionData(diameter_nm=[100.0], intensity=[20.0])

    assert second.flags == []
    assert second.distributions == {}


def test_measurement_serializes_to_plain_dict():
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name="Sample 1", source_files=["run.csv"]),
        summary_metrics=SummaryMetrics(z_average=125.0, pdi=0.18),
        distributions={"intensity": DistributionData(diameter_nm=[100.0], intensity=[99.0])},
        derived_metrics=DerivedMetrics(d50_nm=100.0),
        flags=[MeasurementFlag(label="Moderate PDI", evidence="PDI 0.31")],
    )

    payload = measurement.to_dict()

    assert payload["metadata"]["sample_name"] == "Sample 1"
    assert payload["summary_metrics"]["z_average"] == 125.0
    assert payload["distributions"]["intensity"]["diameter_nm"] == [100.0]
    assert payload["flags"][0]["label"] == "Moderate PDI"


def test_measurement_merge_combines_partial_imports():
    base = Measurement(
        metadata=MeasurementMetadata(sample_name="Sample 1", source_files=["summary.csv"]),
        summary_metrics=SummaryMetrics(z_average=120.0),
    )
    graph = Measurement(
        metadata=MeasurementMetadata(sample_name="Sample 1", source_files=["graph.xlsx"], raw_fields={"Operator": "MT"}),
        summary_metrics=SummaryMetrics(pdi=0.22),
        distributions={"intensity": DistributionData(diameter_nm=[100.0, 200.0], intensity=[20.0, 10.0])},
        flags=[MeasurementFlag(label="Secondary peak")],
    )

    merged = base.merge(graph)

    assert merged is base
    assert merged.metadata.source_files == ["summary.csv", "graph.xlsx"]
    assert merged.metadata.raw_fields == {"Operator": "MT"}
    assert merged.summary_metrics.z_average == 120.0
    assert merged.summary_metrics.pdi == 0.22
    assert merged.distributions["intensity"].intensity == [20.0, 10.0]
    assert [flag.label for flag in merged.flags] == ["Secondary peak"]


def test_measurement_merge_fills_missing_metadata_scalars():
    base = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))
    summary = Measurement(
        metadata=MeasurementMetadata(
            sample_name="Lot 1",
            measurement_datetime="2026-07-01 12:08:20",
            temperature="25",
        )
    )

    merged = base.merge(summary)

    assert merged.metadata.measurement_datetime == "2026-07-01 12:08:20"
    assert merged.metadata.temperature == "25"


def test_measurement_merge_carries_and_fills_angle_summaries():
    base = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))
    summary = Measurement(
        metadata=MeasurementMetadata(sample_name="Lot 1"),
        angle_summaries=[
            AngleSummary(label="Forward 12.78°", angle_degrees=12.78, position="forward", z_average=453.0),
            AngleSummary(label="Back 174.7°", angle_degrees=174.7, position="back", z_average=265.0),
        ],
    )

    base.merge(summary)
    # A later partial fills a missing per-angle field without duplicating the angle.
    base.merge(
        Measurement(
            metadata=MeasurementMetadata(sample_name="Lot 1"),
            angle_summaries=[AngleSummary(label="Forward 12.78°", angle_degrees=12.78, primary_peak_nm=420.2)],
        )
    )

    labels = [summary.label for summary in base.angle_summaries]
    assert labels == ["Forward 12.78°", "Back 174.7°"]
    forward = base.angle_summaries[0]
    assert forward.z_average == 453.0
    assert forward.primary_peak_nm == 420.2
