"""Pure presentation helpers over application read models."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from labassistant.application import DLSAnalysisResult, DLSMeasurementSummary, ExperimentListing


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


def result_payload(result: DLSAnalysisResult) -> dict:
    """Serialize the read model for the local native presentation document."""
    display = build_analysis_display(result)
    status_label, status_tone = result_status(result)
    return {
        "experiment": result.experiment.to_dict(),
        "source_files": list(result.source_files),
        "status": {"label": status_label, "tone": status_tone},
        "measurements": [
            {
                "sample_name": measurement.sample_name,
                "status": measurement.status,
                "z_average": _format_metric(measurement.z_average_nm, " nm"),
                "pdi": _format_metric(measurement.pdi),
                "primary_peak": _format_metric(measurement.primary_peak_nm, " nm"),
                "d50": _format_metric(measurement.d50_nm, " nm"),
                "quality_score": _format_metric(measurement.quality_score),
                "warnings": list(measurement.warnings),
            }
            for measurement in result.measurements
        ],
        "analysis": {
            "summary": list(display.summary),
            "evidence": list(display.evidence),
            "possible_causes": list(display.possible_causes),
            "next_steps": list(display.next_steps),
        },
    }


def persisted_history_payload(listings: Iterable[ExperimentListing]) -> list[dict]:
    """Serialize persisted experiment listings for the timeline document.

    This carries only immutable metadata plus a human-readable saved time. It
    never exposes measurements; the document restores a record by ``record_id``
    through the application boundary when the scientist opens it.
    """
    return [
        {
            "record_id": listing.record_id,
            "label": listing.label,
            "measurement_count": listing.measurement_count,
            "saved_at": listing.saved_at,
            "saved_display": _format_saved_at(listing.saved_at),
        }
        for listing in listings
    ]


def _format_saved_at(saved_at: str) -> str:
    """Render an ISO timestamp as a compact local-looking date/time label."""
    text = (saved_at or "").strip()
    if not text:
        return "Unknown time"
    head = text.split("+", 1)[0].split("Z", 1)[0]
    if "T" in head:
        date_part, time_part = head.split("T", 1)
        return f"{date_part} {time_part[:5]}".strip()
    return head


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
