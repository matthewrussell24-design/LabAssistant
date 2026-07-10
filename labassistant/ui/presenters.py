"""Pure presentation helpers over application read models."""

from __future__ import annotations

from dataclasses import dataclass

from labassistant.application import DLSAnalysisResult, DLSMeasurementSummary


@dataclass(frozen=True)
class AnalysisDisplay:
    summary: tuple[str, ...]
    evidence: tuple[str, ...]
    possible_causes: tuple[str, ...]
    next_steps: tuple[str, ...]


def build_analysis_display(result: DLSAnalysisResult) -> AnalysisDisplay:
    """Organize existing results without adding scientific interpretation."""
    flagged = [measurement for measurement in result.measurements if measurement.warnings]
    summary = (
        f"{result.experiment.measurement_count} measurement{_plural(result.experiment.measurement_count)} imported.",
        f"{result.experiment.observation_count} normalized observation{_plural(result.experiment.observation_count)} available.",
        (
            f"Review signals are present in {len(flagged)} lot{_plural(len(flagged))}."
            if flagged
            else "No measurement warnings were reported."
        ),
    )
    evidence = tuple(_measurement_evidence(measurement) for measurement in result.measurements)
    if result.import_errors:
        evidence += tuple(f"Import note: {error}" for error in result.import_errors)
    causes = (
        "The current read-only contract does not assign causal explanations.",
        "Use formulation, process, and orthogonal-method context before assigning a cause.",
    )
    next_steps = (
        "Review flagged measurements and their source provenance.",
        "Compare or repeat measurements when scientifically appropriate.",
        "Capture experimental context before drawing a conclusion.",
    )
    return AnalysisDisplay(summary, evidence, causes, next_steps)


def result_status(result: DLSAnalysisResult) -> tuple[str, str]:
    """Return a presentation status label and semantic tone."""
    if any(measurement.warnings for measurement in result.measurements):
        return "Review", "warning"
    return "Ready", "success"


def _measurement_evidence(measurement: DLSMeasurementSummary) -> str:
    metrics = [
        f"Z-average {_format_metric(measurement.z_average_nm, ' nm')}",
        f"PDI {_format_metric(measurement.pdi)}",
        f"primary peak {_format_metric(measurement.primary_peak_nm, ' nm')}",
        f"aggregation risk {measurement.aggregation_risk or 'unavailable'}",
    ]
    warning_text = f" Warnings: {', '.join(measurement.warnings)}." if measurement.warnings else ""
    return f"{measurement.sample_name}: {'; '.join(metrics)}.{warning_text}"


def _format_metric(value: float | None, suffix: str = "") -> str:
    return "unavailable" if value is None else f"{value:.3g}{suffix}"


def _plural(count: int) -> str:
    return "" if count == 1 else "s"
