from labassistant.application import DLSAnalysisResult, DLSMeasurementSummary, ExperimentSnapshot
from labassistant.desktop import format_analysis_summary


def test_desktop_summary_formats_application_result_without_scientific_logic():
    result = DLSAnalysisResult(
        experiment=ExperimentSnapshot(
            experiment_id="exp-1",
            label="Desktop proof",
            technique="DLS",
            instrument="DLS",
            measurement_count=1,
            observation_count=2,
            observation_categories={"quality": 2},
        ),
        measurements=(
            DLSMeasurementSummary(
                sample_name="Lot 1",
                status="Review",
                source_files=("summary.xlsx", "intensity.xlsx"),
                z_average_nm=265.2,
                pdi=0.323,
                primary_peak_nm=267.2,
                d50_nm=267.2,
                aggregation_risk="High",
                quality_score=43.4,
                warnings=("High PDI",),
            ),
        ),
        source_files=("summary.xlsx", "intensity.xlsx"),
        import_errors=(),
    )

    summary = format_analysis_summary(result)

    assert "Desktop proof" in summary
    assert "Measurements: 1" in summary
    assert "Observations: 2" in summary
    assert "Primary peak: 267 nm" in summary
    assert "Aggregation risk: High" in summary
