import pandas as pd

from labassistant.models import Measurement, MeasurementMetadata, SummaryMetrics
from labassistant.trend_analysis import (
    analyze_series,
    build_data_story,
    control_chart_table,
    replicate_statistics_table,
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
