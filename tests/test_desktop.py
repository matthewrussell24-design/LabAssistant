from pathlib import Path

from labassistant.application import (
    DLSAnalysisResult,
    DLSMeasurementSummary,
    ExperimentListing,
    ExperimentSnapshot,
)
from labassistant.desktop import analyze_paths_for_display, format_analysis_summary
from labassistant.ui.presenters import (
    build_analysis_display,
    persisted_history_payload,
    result_payload,
    result_status,
)
from labassistant.ui.web_workspace import WORKSPACE_HTML


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


def test_desktop_can_analyze_paths_supplied_by_launcher():
    fixture_dir = Path(__file__).parent / "fixtures"

    summary = analyze_paths_for_display(
        [
            str(fixture_dir / "Orchestra_Zetasizer_Data_Lot_446-01.xlsx"),
            str(fixture_dir / "Size Distribution by Intensity Lot 1.xlsx"),
            str(fixture_dir / "Correlogram lot 1.xlsx"),
        ]
    )

    assert "Measurements: 1" in summary
    assert "Lot 1" in summary
    assert "Primary peak: 267 nm" in summary


def test_analysis_presenter_organizes_existing_evidence_without_inventing_causes():
    result = DLSAnalysisResult(
        experiment=ExperimentSnapshot(
            experiment_id="exp-1",
            label="DLS experiment",
            technique="DLS",
            instrument="DLS",
            measurement_count=1,
            observation_count=1,
            observation_categories={"quality": 1},
        ),
        measurements=(
            DLSMeasurementSummary(
                sample_name="Lot 1",
                status="Review",
                source_files=("summary.xlsx",),
                z_average_nm=359.0,
                pdi=0.323,
                primary_peak_nm=267.0,
                d50_nm=267.0,
                aggregation_risk="High",
                quality_score=43.4,
                warnings=("Dual-angle aggregation",),
            ),
        ),
        source_files=("summary.xlsx",),
        import_errors=(),
    )

    display = build_analysis_display(result)

    assert display.summary == (
        "1 measurement imported.",
        "1 normalized observation available.",
        "Review signals are present in 1 lot.",
    )
    assert "Z-average 359 nm" in display.evidence[0]
    assert "does not assign causal explanations" in display.possible_causes[0]
    assert result_status(result) == ("Review", "warning")

    payload = result_payload(result)
    assert payload["measurements"][0]["primary_peak"] == "267 nm"
    assert payload["status"] == {"label": "Review", "tone": "warning"}


def test_native_workspace_document_has_reusable_dashboard_regions():
    assert 'class="card workspace"' in WORKSPACE_HTML
    assert 'class="card experiment"' in WORKSPACE_HTML
    assert 'class="card analysis"' in WORKSPACE_HTML
    assert 'class="card history"' in WORKSPACE_HTML
    assert "const metric=" in WORKSPACE_HTML
    assert "const section=" in WORKSPACE_HTML
    assert "window.webkit.messageHandlers.labassistant" in WORKSPACE_HTML


def test_native_workspace_document_supports_persisted_history_restore():
    # The Open Existing Experiment action is real now, not a disabled placeholder.
    assert 'id="open-existing"' in WORKSPACE_HTML
    assert "window.labassistantSetPersistedHistory" in WORKSPACE_HTML
    assert "action:'open_experiment'" in WORKSPACE_HTML
    assert "SAVED EXPERIMENTS" in WORKSPACE_HTML
    assert "Persisted history planned" not in WORKSPACE_HTML


def test_persisted_history_payload_exposes_metadata_only_with_readable_time():
    listings = [
        ExperimentListing(
            record_id="rec-1",
            saved_at="2026-07-10T13:05:42+00:00",
            label="Saved run",
            measurement_count=2,
        )
    ]

    payload = persisted_history_payload(listings)

    assert payload == [
        {
            "record_id": "rec-1",
            "label": "Saved run",
            "measurement_count": 2,
            "saved_at": "2026-07-10T13:05:42+00:00",
            "saved_display": "2026-07-10 13:05",
        }
    ]
