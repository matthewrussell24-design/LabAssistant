"""Minimal native desktop shell for the DLS vertical slice."""

from __future__ import annotations

from collections.abc import Sequence

from labassistant.application import DLSAnalysisResult, analyze_dls_dataset


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


def analyze_paths_for_display(paths: Sequence[str]) -> str:
    """Analyze selected local paths and return desktop-ready text."""
    return format_analysis_summary(analyze_dls_dataset(paths))


def run_desktop(initial_paths: Sequence[str] = ()) -> None:
    """Open the native AppKit desktop workspace."""
    from labassistant.ui.macos_window import run_native_workspace

    run_native_workspace(analyze_dls_dataset, initial_paths)


if __name__ == "__main__":
    import sys

    run_desktop(sys.argv[1:])
