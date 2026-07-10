"""Polished desktop workspace assembled from reusable presentation components."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from labassistant.application import DLSAnalysisResult
from labassistant.ui.components import (
    AnalysisSection,
    Card,
    HistoryItem,
    MetricTile,
    StatusBadge,
    WorkspaceAction,
)
from labassistant.ui.presenters import build_analysis_display, result_status


SUPPORTED_DLS_FILE_FILTER = (
    "Supported DLS files (*.csv *.txt *.tsv *.xlsx *.xls);;"
    "CSV files (*.csv);;Excel workbooks (*.xlsx *.xls);;All files (*)"
)


class DesktopWindow(QMainWindow):
    def __init__(
        self,
        analyze_dataset: Callable[[Sequence[str]], DLSAnalysisResult],
        initial_paths: Sequence[str] = (),
    ):
        super().__init__()
        self._analyze_dataset = analyze_dataset
        self._history: list[DLSAnalysisResult] = []
        self._animation: QPropertyAnimation | None = None
        self.setWindowTitle("LabAssistant")
        self.resize(1380, 900)
        self.setMinimumSize(1120, 740)
        self.setCentralWidget(self._build_root())
        if initial_paths:
            self._analyze_paths(initial_paths)

    def _build_root(self) -> QWidget:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 24, 30, 28)
        layout.setSpacing(20)
        layout.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_workspace_panel())
        body.addLayout(self._build_center_column(), stretch=1)
        body.addWidget(self._build_history_panel())
        layout.addLayout(body, stretch=1)
        return root

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand.setSpacing(1)
        eyebrow = QLabel("LABORATORY INTELLIGENCE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("LabAssistant")
        title.setObjectName("displayTitle")
        subtitle = QLabel("The future of discovery, grounded in your evidence.")
        subtitle.setObjectName("pageSubtitle")
        brand.addWidget(eyebrow)
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        badge = QLabel("LOCAL WORKSPACE")
        badge.setObjectName("brandBadge")
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        return header

    def _build_workspace_panel(self) -> Card:
        panel = Card("Workspace", "Start with an experiment, then bring in evidence.")
        panel.setFixedWidth(270)
        new_button = WorkspaceAction("New Experiment", "Clear the active workspace")
        new_button.clicked.connect(self._reset_workspace)
        self.import_button = WorkspaceAction("Import DLS Dataset", "Analyze supported local files", primary=True)
        self.import_button.clicked.connect(self._select_dls_dataset)
        panel.content.addWidget(new_button)
        panel.content.addWidget(self.import_button)
        panel.content.addWidget(WorkspaceAction("Import Chromatography", "Future workflow", enabled=False))
        panel.content.addWidget(WorkspaceAction("Import CSV", "Generic import planned", enabled=False))
        panel.content.addWidget(WorkspaceAction("Open Existing Experiment", "Persisted history planned", enabled=False))
        panel.content.addStretch()
        note = QLabel("Scientific logic remains in the shared LabAssistant core.")
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        panel.content.addWidget(note)
        return panel

    def _build_center_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(18)
        self.experiment_card = Card()
        self.experiment_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.experiment_stack = QStackedWidget()
        self.empty_page = self._build_empty_state()
        self.result_page = self._build_result_state()
        self.experiment_stack.addWidget(self.empty_page)
        self.experiment_stack.addWidget(self.result_page)
        self.experiment_card.content.addWidget(self.experiment_stack)
        column.addWidget(self.experiment_card, stretch=5)
        column.addWidget(self._build_analysis_panel(), stretch=4)
        return column

    def _build_empty_state(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 46, 28, 46)
        layout.setSpacing(10)
        layout.addStretch()
        icon = QLabel("✦")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "color: #3867E8; background: #EEF3FF; border-radius: 28px;"
            "font-size: 24px; min-width: 56px; max-width: 56px; min-height: 56px; max-height: 56px;"
        )
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        title = QLabel("Your current experiment will live here")
        title.setObjectName("cardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        detail = QLabel(
            "Import a supported DLS dataset to assemble measurements, surface observations, "
            "and begin an evidence-grounded review."
        )
        detail.setObjectName("mutedText")
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setMaximumWidth(500)
        layout.addWidget(detail, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_action = WorkspaceAction("Import DLS Dataset", "Select summary, intensity, and correlogram files", primary=True)
        empty_action.setMaximumWidth(340)
        empty_action.clicked.connect(self._select_dls_dataset)
        layout.addWidget(empty_action, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        return page

    def _build_result_state(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 0, 2, 2)
        layout.setSpacing(15)
        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        self.experiment_title = QLabel("Current Experiment")
        self.experiment_title.setObjectName("cardTitle")
        self.experiment_subtitle = QLabel()
        self.experiment_subtitle.setObjectName("mutedText")
        title_box.addWidget(self.experiment_title)
        title_box.addWidget(self.experiment_subtitle)
        heading.addLayout(title_box)
        heading.addStretch()
        self.experiment_badge = StatusBadge("Ready", "success")
        heading.addWidget(self.experiment_badge, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.metric_measurements = MetricTile("Measurements")
        self.metric_observations = MetricTile("Observations")
        self.metric_peak = MetricTile("Primary Peak")
        self.metric_pdi = MetricTile("PDI")
        self.metric_quality = MetricTile("Quality")
        for tile in (
            self.metric_measurements,
            self.metric_observations,
            self.metric_peak,
            self.metric_pdi,
            self.metric_quality,
        ):
            metrics.addWidget(tile)
        layout.addLayout(metrics)

        label = QLabel("MEASUREMENT OVERVIEW")
        label.setObjectName("metricLabel")
        layout.addWidget(label)
        self.measurement_rows = QVBoxLayout()
        self.measurement_rows.setSpacing(8)
        layout.addLayout(self.measurement_rows)
        layout.addStretch()
        return page

    def _build_analysis_panel(self) -> Card:
        panel = Card("Analysis", "Evidence-aware guidance from the current experiment.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.analysis_summary = AnalysisSection("Summary")
        self.analysis_evidence = AnalysisSection("Evidence")
        self.analysis_causes = AnalysisSection("Possible Causes")
        self.analysis_next = AnalysisSection("Suggested Next Steps")
        grid.addWidget(self.analysis_summary, 0, 0)
        grid.addWidget(self.analysis_evidence, 0, 1)
        grid.addWidget(self.analysis_causes, 1, 0)
        grid.addWidget(self.analysis_next, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        panel.content.addLayout(grid)
        return panel

    def _build_history_panel(self) -> Card:
        panel = Card("History", "Recent work from this desktop session.")
        panel.setFixedWidth(270)
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(8)
        self.history_empty = QLabel("No experiments yet.\nImported analyses will appear here.")
        self.history_empty.setObjectName("mutedText")
        self.history_empty.setWordWrap(True)
        self.history_layout.addWidget(self.history_empty)
        self.history_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.history_container)
        panel.content.addWidget(scroll)
        footer = QLabel("Persisted restore will be added through an application contract.")
        footer.setObjectName("mutedText")
        footer.setWordWrap(True)
        panel.content.addWidget(footer)
        return panel

    def _select_dls_dataset(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select DLS dataset files",
            "",
            SUPPORTED_DLS_FILE_FILTER,
        )
        if paths:
            self._analyze_paths(paths)

    def _analyze_paths(self, paths: Sequence[str]) -> None:
        self.import_button.setEnabled(False)
        self.import_button.setText("Analyzing…\nBuilding the experiment workspace")
        QApplication.processEvents()
        try:
            result = self._analyze_dataset(paths)
        except Exception as error:
            QMessageBox.critical(self, "DLS analysis failed", str(error))
            return
        finally:
            self.import_button.setText("Import DLS Dataset\nAnalyze supported local files")
            self.import_button.setEnabled(True)
        self._history.insert(0, result)
        self._add_history_item(result)
        self.show_result(result)

    def show_result(self, result: DLSAnalysisResult) -> None:
        status, tone = result_status(result)
        self.experiment_title.setText(result.experiment.label)
        self.experiment_subtitle.setText(
            f"{result.experiment.technique or 'Unknown technique'}  ·  "
            f"{len(result.source_files)} source file{'s' if len(result.source_files) != 1 else ''}"
        )
        self.experiment_badge.set_status(status, tone)
        first = result.measurements[0] if result.measurements else None
        self.metric_measurements.set_value(str(result.experiment.measurement_count))
        self.metric_observations.set_value(str(result.experiment.observation_count))
        self.metric_peak.set_value(_format_metric(first.primary_peak_nm if first else None, " nm"))
        self.metric_pdi.set_value(_format_metric(first.pdi if first else None))
        self.metric_quality.set_value(_format_metric(first.quality_score if first else None))
        self._populate_measurement_rows(result)
        display = build_analysis_display(result)
        self.analysis_summary.set_items(display.summary)
        self.analysis_evidence.set_items(display.evidence)
        self.analysis_causes.set_items(display.possible_causes)
        self.analysis_next.set_items(display.next_steps)
        self.experiment_stack.setCurrentWidget(self.result_page)
        self._fade_in(self.result_page)

    def _populate_measurement_rows(self, result: DLSAnalysisResult) -> None:
        _clear_layout(self.measurement_rows)
        for measurement in result.measurements:
            row = QFrame()
            row.setObjectName("subtlePanel")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(14, 11, 14, 11)
            name_box = QVBoxLayout()
            name = QLabel(measurement.sample_name)
            name.setObjectName("sectionTitle")
            detail = QLabel(
                f"Z-average {_format_metric(measurement.z_average_nm, ' nm')}  ·  "
                f"D50 {_format_metric(measurement.d50_nm, ' nm')}"
            )
            detail.setObjectName("mutedText")
            name_box.addWidget(name)
            name_box.addWidget(detail)
            layout.addLayout(name_box)
            layout.addStretch()
            row_status = StatusBadge(measurement.status, "warning" if measurement.warnings else "success")
            layout.addWidget(row_status)
            self.measurement_rows.addWidget(row)

    def _add_history_item(self, result: DLSAnalysisResult) -> None:
        self.history_empty.hide()
        item = HistoryItem(
            result.experiment.label,
            f"Just now  ·  {result.experiment.measurement_count} measurement"
            f"{'s' if result.experiment.measurement_count != 1 else ''}",
            result,
        )
        item.activated.connect(self.show_result)
        self.history_layout.insertWidget(0, item)

    def _reset_workspace(self) -> None:
        self.experiment_stack.setCurrentWidget(self.empty_page)
        self.analysis_summary.set_items(())
        self.analysis_evidence.set_items(())
        self.analysis_causes.set_items(())
        self.analysis_next.set_items(())

    def _fade_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(240)
        animation.setStartValue(0.15)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._animation = animation
        animation.start()


def _format_metric(value: float | None, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.3g}{suffix}"


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
