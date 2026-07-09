import pandas as pd

from labassistant.models import AngleSummary, Measurement, MeasurementMetadata, SummaryMetrics
from labassistant.trend_analysis import (
    analyze_series,
    build_data_story,
    build_forward_scatter_trend_analysis,
    control_chart_table,
    forward_angle_summary,
    pearson_correlation,
    replicate_statistics_table,
    relationship_strength,
)
from labassistant.view_models import ParsedSample, build_metrics_table


def test_analyze_series_calculates_stats_trend_limits_and_change_point():
    analysis = analyze_series("Z-Average", [100, 101, 102, 122, 124, 126], unit="nm")

    assert round(analysis.mean, 2) == 112.5
    assert round(analysis.sd, 2) == 12.68
    assert round(analysis.rsd_percent, 1) == 11.3
    assert analysis.drift == "increasing"
    assert analysis.change_point_index == 3
    assert analysis.warning_limits is not None
    assert analysis.action_limits is not None


def test_analyze_series_uses_mad_for_single_outlier():
    analysis = analyze_series("PDI", [0.20, 0.21, 0.205, 0.60, 0.208], labels=["r1", "r2", "r3", "r4", "r5"])

    assert analysis.outlier_method == "MAD"
    assert analysis.outlier_indices == [3]
    assert analysis.drift == "outlier"


def make_sample(name: str, z_average: float, pdi: float, replicate_z: list[float]) -> ParsedSample:
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name=name),
        summary_metrics=SummaryMetrics(z_average=z_average, pdi=pdi),
        provenance={"replicate_metrics": {"Z-Average": replicate_z}},
    )
    metrics = {
        "Data Type": "Measurement Summary",
        "Z-Average": z_average,
        "PDI": pdi,
        "Max Z-Average": max(replicate_z),
        "Max PDI": None,
        "Measurement Count": len(replicate_z),
        "Scattering Angles": None,
        "Primary Peak": z_average,
        "Secondary Peak": None,
        "Peak Count": None,
        "Peak Width Ratio": None,
        "Peak Symmetry": None,
        "Count Rate": None,
        "Tail Index": 0.0,
        "Width Ratio": 3.0,
        "Skewness": None,
        "Aggregation Risk": None,
        "Aggregation Index": None,
        "Quality Score": 95.0,
        "D10": 80.0,
        "D50": z_average,
        "D90": 140.0,
        "Diameter Column": None,
        "Intensity Column": None,
        "Volume Column": None,
        "Number Column": None,
        "Preferred Distribution": None,
        "Z-Average Column": "Z-Average (nm)",
        "PDI Column": "PDI",
        "Scattering Angle Column": None,
        "Measurement Date": None,
        "Correlogram Noise": None,
    }
    return ParsedSample(
        name=name,
        file_name=f"{name}.csv",
        data=pd.DataFrame(),
        metadata={},
        metrics=metrics,
        warnings=[],
        source_text="",
        measurement=measurement,
    )


def make_forward_sample(name: str, forward_z: float | None, forward_pdi: float | None) -> ParsedSample:
    sample = make_sample(name, z_average=forward_z or 100, pdi=forward_pdi or 0.2, replicate_z=[100, 101, 102])
    sample.measurement.angle_summaries = [
        AngleSummary(label="Back 173°", angle_degrees=173.0, position="back", z_average=250.0, pdi=0.30),
        AngleSummary(label="Forward 12.8°", angle_degrees=12.8, position="forward", z_average=forward_z, pdi=forward_pdi),
    ]
    return sample


def test_data_story_and_tables_surface_replicate_variability():
    samples = [
        make_sample("A", 100, 0.20, [99, 100, 101]),
        make_sample("B", 110, 0.21, [106, 110, 121]),
        make_sample("C", 125, 0.22, [120, 126, 129]),
    ]
    metrics = build_metrics_table(samples)

    story = build_data_story(samples, metrics)
    replicate_table = replicate_statistics_table(samples)
    chart_table = control_chart_table(samples, metrics)

    assert any("Z-Average is increasing" in item for item in story["What Changed"])
    assert set(replicate_table["Metric"]) == {"Z-Average"}
    assert replicate_table.loc[replicate_table["Sample"] == "B", "%RSD"].iloc[0] > 5
    assert not chart_table.empty
    assert {"Warning Low", "Warning High", "Action Low", "Action High"}.issubset(chart_table.columns)


def test_forward_scatter_trend_uses_explicit_sample_time_mapping():
    samples = [
        make_forward_sample("Sample A", 100.0, 0.20),
        make_forward_sample("Sample B", 160.0, 0.30),
        make_forward_sample("Sample C", 220.0, 0.40),
    ]

    analysis = build_forward_scatter_trend_analysis(samples, {"Sample A": 10, "Sample B": 20, "Sample C": 30})

    assert [point.sample for point in analysis.points] == ["Sample A", "Sample B", "Sample C"]
    assert analysis.z_average.valid_count == 3
    assert analysis.z_average.pearson_r is not None
    assert round(analysis.z_average.pearson_r, 2) == 1.0
    assert analysis.z_average.relationship == "strong"
    assert analysis.pdi.relationship == "strong"
    assert "correlation only" in analysis.z_average.message


def test_forward_scatter_trend_requires_three_distinct_circulation_times():
    samples = [
        make_forward_sample("Sample A", 100.0, 0.20),
        make_forward_sample("Sample B", 150.0, 0.30),
        make_forward_sample("Sample C", 220.0, 0.45),
    ]

    analysis = build_forward_scatter_trend_analysis(samples, {"Sample A": 10, "Sample B": 10, "Sample C": 20})

    assert analysis.z_average.pearson_r is None
    assert "3 distinct circulation times" in analysis.z_average.message


def test_forward_scatter_trend_ignores_samples_without_entered_time():
    samples = [
        make_forward_sample("Sample A", 100.0, 0.20),
        make_forward_sample("Sample B", 150.0, 0.30),
        make_forward_sample("Sample C", 220.0, 0.45),
    ]

    analysis = build_forward_scatter_trend_analysis(samples, {"Sample A": 10, "Sample B": 20})

    assert [point.sample for point in analysis.points] == ["Sample A", "Sample B"]
    assert analysis.z_average.pearson_r is None
    assert "At least 3 valid samples" in analysis.z_average.message


def test_forward_angle_summary_falls_back_to_low_angle_metadata():
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name="fallback"),
        summary_metrics=SummaryMetrics(z_average=100.0, pdi=0.2),
        angle_summaries=[
            AngleSummary(label="Back 173°", angle_degrees=173.0, z_average=260.0),
            AngleSummary(label="Forward 12°", angle_degrees=12.0, z_average=120.0),
        ],
    )

    summary = forward_angle_summary(measurement)

    assert summary is not None
    assert summary.label == "Forward 12°"


def test_pearson_and_relationship_strength_helpers_are_restrained():
    assert round(pearson_correlation([1, 2, 3], [1, 3, 5]), 2) == 1.0
    assert relationship_strength(0.1) == "weak"
    assert relationship_strength(0.5) == "moderate"
    assert relationship_strength(-0.9) == "strong"
