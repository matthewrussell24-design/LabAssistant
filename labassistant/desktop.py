"""Minimal native desktop shell for the DLS vertical slice."""

from __future__ import annotations

import argparse
import atexit
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import Callable, TextIO

from labassistant.application import DLSAnalysisResult, analyze_dls_dataset
from labassistant.desktop_read_sharing import (
    DesktopReadBrokerOwner,
    DesktopReadSharingStatus,
    SHUTDOWN_FAILED,
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


def analyze_paths_for_display(paths: Sequence[str]) -> str:
    """Analyze selected local paths and return desktop-ready text."""
    return format_analysis_summary(analyze_dls_dataset(paths))


def run_desktop(
    initial_paths: Sequence[str] = (),
    *,
    share_local_reads: bool = False,
    read_socket: Path | str | None = None,
    owner_factory: Callable[..., DesktopReadBrokerOwner] = DesktopReadBrokerOwner,
    status_stream: TextIO = sys.stderr,
) -> DesktopReadSharingStatus | None:
    """Open the native AppKit desktop workspace."""
    from labassistant.ui.macos_window import run_native_workspace

    if not share_local_reads:
        run_native_workspace(analyze_dls_dataset, initial_paths)
        return None

    owner = owner_factory(read_socket)
    status = owner.start()
    print(status.message(), file=status_stream)
    atexit.register(owner.close)
    try:
        run_native_workspace(
            analyze_dls_dataset,
            initial_paths,
            termination_callback=owner.close,
        )
    finally:
        final_status = owner.close()
        atexit.unregister(owner.close)
        if final_status.state == SHUTDOWN_FAILED:
            print(final_status.message(), file=status_stream)
    return status


def parse_desktop_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open the LabAssistant desktop")
    parser.add_argument(
        "--share-local-reads",
        action="store_true",
        help="share the stable read-only API for this desktop session",
    )
    parser.add_argument(
        "--read-socket",
        type=Path,
        help="override the local read socket (requires --share-local-reads)",
    )
    parser.add_argument("paths", nargs="*", help="initial DLS dataset files")
    args = parser.parse_args(argv)
    if args.read_socket is not None and not args.share_local_reads:
        parser.error("--read-socket requires --share-local-reads")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_desktop_args(argv)
    run_desktop(
        args.paths,
        share_local_reads=args.share_local_reads,
        read_socket=args.read_socket,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
