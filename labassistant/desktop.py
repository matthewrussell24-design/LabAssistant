"""Minimal native desktop shell for the DLS vertical slice."""

from __future__ import annotations

from labassistant.application import DLSAnalysisResult, analyze_dls_dataset


SUPPORTED_DLS_FILE_FILTER = (
    "Supported DLS files (*.csv *.txt *.tsv *.xlsx *.xls);;"
    "CSV files (*.csv);;Excel workbooks (*.xlsx *.xls);;All files (*)"
)


def format_analysis_summary(result: DLSAnalysisResult) -> str:
    """Format an application result for compact human review."""
    snapshot = result.experiment
    lines = [
        snapshot.label,
        f"Technique: {snapshot.technique or 'Unknown'}",
        f"Measurements: {snapshot.measurement_count}",
        f"Observations: {snapshot.observation_count}",
        "",
    ]
    for measurement in result.measurements:
        lines.extend(
            [
                measurement.sample_name,
                f"  Status: {measurement.status}",
                f"  Z-average: {_format_metric(measurement.z_average_nm, ' nm')}",
                f"  PDI: {_format_metric(measurement.pdi)}",
                f"  Primary peak: {_format_metric(measurement.primary_peak_nm, ' nm')}",
                f"  D50: {_format_metric(measurement.d50_nm, ' nm')}",
                f"  Aggregation risk: {measurement.aggregation_risk or 'Unavailable'}",
                f"  Quality score: {_format_metric(measurement.quality_score)}",
                f"  Warnings: {', '.join(measurement.warnings) if measurement.warnings else 'None'}",
                "",
            ]
        )
    if result.import_errors:
        lines.append("Import notes:")
        lines.extend(f"  • {error}" for error in result.import_errors)
    return "\n".join(lines).rstrip()


def _format_metric(value: float | None, suffix: str = "") -> str:
    return "Unavailable" if value is None else f"{value:.3g}{suffix}"


def run_desktop() -> None:
    """Open the native Qt desktop prototype."""
    import sys

    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QLabel,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    application = QApplication.instance() or QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("LabAssistant Desktop Prototype")
    window.resize(760, 560)
    window.setMinimumSize(620, 420)

    layout = QVBoxLayout(window)
    title = QLabel("LabAssistant")
    title_font = title.font()
    title_font.setPointSize(20)
    title_font.setBold(True)
    title.setFont(title_font)
    layout.addWidget(title)
    layout.addWidget(QLabel("Select an existing DLS dataset to run the shared LabAssistant analysis."))

    select_button = QPushButton("Select DLS Dataset…")
    layout.addWidget(select_button)
    output = QTextEdit()
    output.setReadOnly(True)
    output.setPlainText("No dataset selected.")
    layout.addWidget(output, stretch=1)

    def select_dataset() -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            window,
            "Select DLS dataset files",
            "",
            SUPPORTED_DLS_FILE_FILTER,
        )
        if not paths:
            return
        try:
            result = analyze_dls_dataset(paths)
        except Exception as error:
            QMessageBox.critical(window, "DLS analysis failed", str(error))
            return
        output.setPlainText(format_analysis_summary(result))

    select_button.clicked.connect(select_dataset)
    window.show()
    application.exec()


if __name__ == "__main__":
    run_desktop()
