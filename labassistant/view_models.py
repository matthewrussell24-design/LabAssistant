"""Compatibility facade for the original DLS Streamlit view-model API."""

from labassistant.dls_evidence import (
    DLSWorkspaceEvidence,
    build_angle_table,
    build_metrics_table,
    parse_uploaded_file,
    sample_from_measurement,
    sample_status,
)

# Preserve the established constructor/import name for Streamlit and callers.
ParsedSample = DLSWorkspaceEvidence

__all__ = [
    "ParsedSample",
    "build_angle_table",
    "build_metrics_table",
    "parse_uploaded_file",
    "sample_from_measurement",
    "sample_status",
]
