import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from labassistant.application import DLSAnalysisResult, DLSMeasurementSummary, ExperimentSnapshot
from labassistant.ui.components import AnalysisSection, Card, HistoryItem, MetricTile, StatusBadge, WorkspaceAction
from labassistant.ui.desktop_window import DesktopWindow
from labassistant.ui.theme import APP_STYLESHEET


def _application():
    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(APP_STYLESHEET)
    return application


def _result():
    return DLSAnalysisResult(
        experiment=ExperimentSnapshot(
            experiment_id="exp-1",
            label="DLS Stability Study",
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
        source_files=("summary.xlsx", "intensity.xlsx", "correlogram.xlsx"),
        import_errors=(),
    )


def test_reusable_desktop_components_construct_under_qt():
    _application()

    assert Card("Workspace").objectName() == "card"
    assert StatusBadge("Review", "warning").property("tone") == "warning"
    assert MetricTile("PDI", "0.323").value_label.text() == "0.323"
    assert WorkspaceAction("Import DLS", "Select files").isEnabled()
    assert HistoryItem("Run", "Just now", object()).objectName() == "historyItem"
    assert AnalysisSection("Summary", ["One measurement imported."]).layout.count() == 2


def test_desktop_window_populates_cards_and_session_history():
    _application()
    result = _result()
    window = DesktopWindow(lambda paths: result)

    window.show_result(result)
    window._add_history_item(result)

    assert window.experiment_title.text() == "DLS Stability Study"
    assert window.metric_measurements.value_label.text() == "1"
    assert window.metric_peak.value_label.text() == "267 nm"
    assert window.experiment_badge.text() == "Review"
    assert window.history_layout.count() == 3
    window.close()
