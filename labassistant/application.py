from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Callable
from uuid import uuid4

from labassistant.context_engine import (
    DEFAULT_KNOWLEDGE_STORE_PATH,
    ContextRetriever,
    KnowledgeStore,
    ResearchJournal,
)
from labassistant.chromatography import (
    mass_balance_hypotheses,
    observations_from_mass_balance_assessment,
)
from labassistant.history import (
    DEFAULT_HISTORY_PATH,
    compare_experiments as compare_history_experiments,
    chromatography_measurements_from_record,
    find_similar_samples,
    history_table,
    latest_experiment,
    load_experiment_record,
    load_history,
    measurements_from_record,
    save_experiment as save_history_experiment,
    trend_table,
)
from labassistant.importers.chromatography import (
    assess_chromatography_mass_balance,
    chromatography_observations,
    parse_chromatography_csv,
    peak_area_trend_table,
    total_area_trend_table,
)
from labassistant.importers.openlab_olax import build_experiment_from_olax
from labassistant.importers.filtration import parse_filtration_csv
from labassistant.filtration import observations_from_filtration_measurement
from labassistant.importers.measurement_importer import build_import_preview, import_measurement_groups
from labassistant.investigator import investigate as investigate_domain_experiment
from labassistant.interpretation import (
    build_ai_summary,
    build_data_analysis,
    build_decision_brief,
)
from labassistant.models import (
    ChromatographyMeasurement,
    Experiment,
    FiltrationMeasurement,
    MassBalanceAssessment,
    Measurement,
    Observation,
)
from labassistant.observations import observations_from_samples
from labassistant.quality import STATUS_NORMAL, STATUS_REVIEW, STATUS_WATCH
from labassistant.trend_analysis import (
    build_data_story,
    control_chart_table,
    replicate_statistics_table,
)
from labassistant.view_models import build_metrics_table, sample_from_measurement, sample_status


APP_NAME = "LabAssistant"
APP_DIRECTION = "standalone_experiment_intelligence_app"
HUMAN_APP_SURFACE = "human_first_standalone_application"
AGENT_ACCESS_STATUS = "planned_foundation"
AGENT_API_VERSION = "0.1-draft"


@dataclass(frozen=True)
class AgentAccessPolicy:
    """Current boundaries for future agent access.

    This is intentionally a policy object, not an agent runtime. The application
    should expose stable experiment operations before it exposes autonomous
    actions.
    """

    api_version: str = AGENT_API_VERSION
    status: str = AGENT_ACCESS_STATUS
    intended_clients: list[str] = field(default_factory=lambda: ["LabAssistant UI", "future local agents"])
    stable_inputs: list[str] = field(default_factory=lambda: ["Experiment", "Observation"])
    stable_outputs: list[str] = field(default_factory=lambda: ["ExperimentSnapshot"])
    current_non_goals: list[str] = field(
        default_factory=lambda: [
            "autonomous lab operation",
            "remote control of instruments",
            "LLM prompt orchestration",
            "network service or external API server",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentSnapshot:
    """Small read-only summary for UI shells and future agent clients."""

    experiment_id: str
    label: str
    technique: str | None
    instrument: str | None
    measurement_count: int
    observation_count: int
    observation_categories: dict[str, int]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSMeasurementSummary:
    """Concise read model for one imported DLS lot."""

    sample_name: str
    status: str
    source_files: tuple[str, ...]
    z_average_nm: float | None
    pdi: float | None
    primary_peak_nm: float | None
    d50_nm: float | None
    aggregation_risk: str | None
    quality_score: float | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSAnalysisResult:
    """Toolkit-independent result returned to local human interfaces."""

    experiment: ExperimentSnapshot
    measurements: tuple[DLSMeasurementSummary, ...]
    source_files: tuple[str, ...]
    import_errors: tuple[str, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment.to_dict(),
            "measurements": [measurement.to_dict() for measurement in self.measurements],
            "source_files": list(self.source_files),
            "import_errors": list(self.import_errors),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class DLSUploadFileRead:
    """Immutable classification and readable-source diagnostics for one upload."""

    file_name: str
    file_type: str
    source_text: str
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSUploadGroupRead:
    """Immutable multi-file grouping summary for one detected DLS lot."""

    lot: str
    status: str
    summary_files: tuple[DLSUploadFileRead, ...]
    intensity_files: tuple[DLSUploadFileRead, ...]
    correlogram_files: tuple[DLSUploadFileRead, ...]
    files: tuple[DLSUploadFileRead, ...]

    def preview_row(self) -> dict[str, str]:
        return {
            "Lot": self.lot,
            "Summary file": self.summary_files[0].file_name if self.summary_files else "",
            "Intensity file": self.intensity_files[0].file_name if self.intensity_files else "",
            "Correlogram file": self.correlogram_files[0].file_name if self.correlogram_files else "",
            "Status": self.status,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "lot": self.lot,
            "status": self.status,
            "summary_files": [item.to_dict() for item in self.summary_files],
            "intensity_files": [item.to_dict() for item in self.intensity_files],
            "correlogram_files": [item.to_dict() for item in self.correlogram_files],
            "files": [item.to_dict() for item in self.files],
        }


@dataclass(frozen=True)
class DLSUploadImportResult:
    """Versioned uploaded-DLS preview plus reviewed copy-on-access evidence."""

    groups: tuple[DLSUploadGroupRead, ...]
    measurements: tuple[DLSMeasurementSummary, ...]
    source_files: tuple[str, ...]
    import_errors: tuple[str, ...]
    _samples: tuple[Any, ...] = field(repr=False, compare=False)
    api_version: str = AGENT_API_VERSION

    def restore_samples(self) -> list[Any]:
        return deepcopy(list(self._samples))

    def preview_rows(self) -> list[dict[str, str]]:
        return [group.preview_row() for group in self.groups]

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [group.to_dict() for group in self.groups],
            "measurements": [measurement.to_dict() for measurement in self.measurements],
            "source_files": list(self.source_files),
            "import_errors": list(self.import_errors),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class DLSAttentionRow:
    """Immutable DLS screening rank for one parsed sample."""

    sample_name: str
    status: str
    attention_score: float
    reason: str
    warnings: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSDecisionRanking:
    """Versioned DLS-specific decision summary without pandas output."""

    best_candidate: str
    attention_candidate: str
    flagged_count: int
    sample_count: int
    review_samples: str
    next_check: str
    unusual_changes: tuple[str, ...]
    attention_rows: tuple[DLSAttentionRow, ...]
    api_version: str = AGENT_API_VERSION

    @property
    def flagged_label(self) -> str:
        return f"{self.flagged_count} of {self.sample_count}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_candidate": self.best_candidate,
            "attention_candidate": self.attention_candidate,
            "flagged_count": self.flagged_count,
            "sample_count": self.sample_count,
            "review_samples": self.review_samples,
            "next_check": self.next_check,
            "unusual_changes": list(self.unusual_changes),
            "attention_rows": [row.to_dict() for row in self.attention_rows],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class DLSNarrativeSection:
    """One ordered, presentation-neutral section of deterministic DLS text."""

    heading: str
    bullets: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"heading": self.heading, "bullets": list(self.bullets)}


@dataclass(frozen=True)
class DLSNarrative:
    """Versioned DLS findings, analysis, and trend story without pandas output."""

    automated_findings: tuple[DLSNarrativeSection, ...]
    data_story: tuple[DLSNarrativeSection, ...]
    detailed_analysis: tuple[DLSNarrativeSection, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "automated_findings": [section.to_dict() for section in self.automated_findings],
            "data_story": [section.to_dict() for section in self.data_story],
            "detailed_analysis": [section.to_dict() for section in self.detailed_analysis],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class DLSHealthOverview:
    """Versioned DLS screening overview without pandas output."""

    screening_score: int
    sample_count: int
    flagged_count: int
    review_count: int
    median_z_average_nm: float | None
    median_tail_percent: float | None
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSControlChartRow:
    """Immutable control-limit assessment for one DLS metric value."""

    sample_name: str
    metric: str
    value: float
    mean: float
    warning_low: float
    warning_high: float
    action_low: float
    action_high: float
    zone: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSReplicateStatisticsRow:
    """Immutable replicate-series statistics for one sample metric."""

    sample_name: str
    metric: str
    count: int
    mean: float | None
    standard_deviation: float | None
    relative_standard_deviation_percent: float | None
    drift: str
    outliers: str
    change_point: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DLSTrendDiagnostics:
    """Versioned DLS control-chart and replicate diagnostics without pandas."""

    control_chart_rows: tuple[DLSControlChartRow, ...]
    replicate_statistics_rows: tuple[DLSReplicateStatisticsRow, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_chart_rows": [row.to_dict() for row in self.control_chart_rows],
            "replicate_statistics_rows": [
                row.to_dict() for row in self.replicate_statistics_rows
            ],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ChromatographyMeasurementSummary:
    """Concise immutable summary of one persisted chromatography injection."""

    sample_name: str
    technique: str
    timepoint: str | None
    injection_id: str | None
    method_name: str | None
    replicate_id: str | None
    source_files: tuple[str, ...]
    peak_count: int
    chromatogram_trace_count: int
    total_area: float | None
    parent_peak_id: str | None
    signal_file_count: int = 0
    raw_data_file: str | None = None
    acquired_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChromatographyRestoreResult:
    """Versioned read model rebuilt from persisted chromatography evidence."""

    record_id: str
    saved_at: str
    experiment: ExperimentSnapshot
    measurements: tuple[ChromatographyMeasurementSummary, ...]
    source_files: tuple[str, ...]
    hypotheses: tuple[str, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "saved_at": self.saved_at,
            "experiment": self.experiment.to_dict(),
            "measurements": [measurement.to_dict() for measurement in self.measurements],
            "source_files": list(self.source_files),
            "hypotheses": list(self.hypotheses),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ChromatographyAssessmentRead:
    sample_name: str
    parent_area_percent: float | None
    known_impurity_area_percent: float | None
    unknown_area_percent: float | None
    total_area_change_percent: float | None
    replicate_rsd_percent: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChromatographyTrendPoint:
    timepoint: str
    parent_area_percent: float | None
    known_impurity_area_percent: float | None
    unknown_area_percent: float | None
    total_area: float | None
    parent_retention_time_min: float | None
    change_vs_start_percent: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChromatographySourceSummary:
    detector_file_count: int
    peak_table_file_count: int
    acquisition_method_file_count: int
    audit_file_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChromatographyAnalysisResult:
    """Toolkit-independent CSV/OpenLab chromatography analysis result."""

    source_kind: str
    source_name: str
    experiment: ExperimentSnapshot
    measurements: tuple[ChromatographyMeasurementSummary, ...]
    observations: tuple[InvestigationObservation, ...]
    hypotheses: tuple[str, ...]
    unsupported_sections: tuple[str, ...]
    assessment: ChromatographyAssessmentRead | None
    trends: tuple[ChromatographyTrendPoint, ...]
    source_summary: ChromatographySourceSummary
    _experiment: Experiment = field(repr=False, compare=False)
    api_version: str = AGENT_API_VERSION

    def restore_experiment(self) -> Experiment:
        return deepcopy(self._experiment)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_name": self.source_name,
            "experiment": self.experiment.to_dict(),
            "measurements": [measurement.to_dict() for measurement in self.measurements],
            "observations": [observation.to_dict() for observation in self.observations],
            "hypotheses": list(self.hypotheses),
            "unsupported_sections": list(self.unsupported_sections),
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "trends": [point.to_dict() for point in self.trends],
            "source_summary": self.source_summary.to_dict(),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class FiltrationTraceRead:
    time_values: tuple[float, ...]
    time_unit: str | None
    time_minutes: tuple[float, ...]
    pressure_values: tuple[float, ...]
    pressure_unit: str | None
    pressure_kpa: tuple[float, ...]
    flow_rate_values: tuple[float, ...]
    flow_rate_unit: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("time_values", "time_minutes", "pressure_values", "pressure_kpa", "flow_rate_values"):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True)
class FiltrationMeasurementSummary:
    sample_name: str
    difficulty_score: float | None
    filtration_time_minutes: float | None
    pressure: float | None
    pressure_unit: str | None
    pressure_kpa: float | None
    filter_type: str | None
    clogging_observed: bool | None
    notes: str | None
    source: str
    source_file: str | None
    warnings: tuple[str, ...]
    trace: FiltrationTraceRead | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["trace"] = self.trace.to_dict() if self.trace else None
        return payload


@dataclass(frozen=True)
class FiltrationImportRead:
    source_name: str | None
    measurements: tuple[FiltrationMeasurementSummary, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    missing_columns: tuple[str, ...]
    unsupported_columns: tuple[str, ...]
    _measurements: tuple[FiltrationMeasurement, ...] = field(repr=False, compare=False)
    api_version: str = AGENT_API_VERSION

    def restore_measurements(self) -> list[FiltrationMeasurement]:
        return deepcopy(list(self._measurements))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "measurements": [measurement.to_dict() for measurement in self.measurements],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "missing_columns": list(self.missing_columns),
            "unsupported_columns": list(self.unsupported_columns),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class RetrievedExperiment:
    """Read-only persisted record metadata with copy-on-access measurements."""

    record_id: str
    saved_at: str
    label: str
    measurement_count: int
    _measurements: tuple[Measurement, ...] = field(repr=False, compare=False)
    api_version: str = AGENT_API_VERSION

    def restore_measurements(self) -> list[Measurement]:
        """Return newly reconstructed, editable measurements for a caller."""

        from copy import deepcopy

        return deepcopy(list(self._measurements))

    def to_dict(self) -> dict[str, Any]:
        """Return stable metadata without exposing mutable measurements."""

        return {
            "record_id": self.record_id,
            "saved_at": self.saved_at,
            "label": self.label,
            "measurement_count": self.measurement_count,
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ExperimentListing:
    """Read-only persisted history entry for timeline browsing.

    The listing is metadata only. It never carries mutable measurements, so a
    timeline can render every saved experiment without a caller being able to
    edit persisted evidence. Callers restore full editable measurements through
    ``retrieve_experiment`` (or a technique restore helper) using ``record_id``.
    """

    record_id: str
    saved_at: str
    label: str
    measurement_count: int
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentComparisonRow:
    """Immutable sample-level drift evidence for two experiments."""

    sample_name: str
    z_average_nm: float | None
    previous_z_average_nm: float | None
    z_change_percent: float | None
    pdi: float | None
    previous_pdi: float | None
    pdi_change: float | None
    drift: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentComparison:
    """Versioned, read-only comparison against persisted history."""

    baseline_record_id: str | None
    baseline_label: str | None
    baseline_saved_at: str | None
    rows: tuple[ExperimentComparisonRow, ...]
    drifted_sample_count: int
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_record_id": self.baseline_record_id,
            "baseline_label": self.baseline_label,
            "baseline_saved_at": self.baseline_saved_at,
            "rows": [row.to_dict() for row in self.rows],
            "drifted_sample_count": self.drifted_sample_count,
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class RelatedExperimentMatch:
    """Immutable saved-sample match returned by related-experiment search."""

    experiment_label: str
    saved_at: str
    sample_name: str
    z_average_nm: float | None
    pdi: float | None
    primary_peak_nm: float | None
    distance: float
    similarity_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelatedExperiments:
    """Versioned, read-only ranked matches for one query measurement."""

    query_sample_name: str
    matches: tuple[RelatedExperimentMatch, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_sample_name": self.query_sample_name,
            "matches": [match.to_dict() for match in self.matches],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class HistorySummary:
    """Immutable experiment-level row for persisted history displays."""

    record_id: str
    saved_at: str
    experiment_label: str
    measurement_count: int
    flagged_count: int
    review_count: int
    median_z_average_nm: float | None
    median_pdi: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HistoryTrendPoint:
    """Immutable sample metric point in persisted append order."""

    saved_at: str
    experiment_label: str
    sample_name: str | None
    z_average_nm: float | None
    pdi: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HistoryOverview:
    """Versioned history summary and trend evidence for interface shells."""

    summaries: tuple[HistorySummary, ...]
    trend_points: tuple[HistoryTrendPoint, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "summaries": [row.to_dict() for row in self.summaries],
            "trend_points": [point.to_dict() for point in self.trend_points],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class InvestigationFinding:
    """Immutable answer to one canonical Investigator question."""

    question: str
    answer: str
    details: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"question": self.question, "answer": self.answer, "details": list(self.details)}


@dataclass(frozen=True)
class InvestigationObservation:
    """Immutable normalized evidence retained with investigation provenance."""

    label: str
    category: str
    evidence: str
    sample_name: str | None
    severity: str
    confidence: str
    source_type: str
    source_id: str | None
    recommendation: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObservationRead:
    """Immutable normalized finding returned by observation generation."""

    label: str
    category: str
    evidence: str
    sample_name: str | None
    severity: str
    confidence: str
    source_type: str
    source_id: str | None
    recommendation: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObservationGenerationResult:
    """Technique-aware observation output with copy-on-access domain evidence."""

    technique: str
    observations: tuple[ObservationRead, ...]
    _domain_observations: tuple[Observation, ...] = field(repr=False, compare=False)
    api_version: str = AGENT_API_VERSION

    def restore_observations(self) -> list[Observation]:
        return deepcopy(list(self._domain_observations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique": self.technique,
            "observations": [observation.to_dict() for observation in self.observations],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ExperimentInvestigation:
    """Versioned read-only Investigator result for application clients."""

    experiment_id: str
    what_happened: str
    is_complete: bool
    is_interpretable: bool
    completeness_gaps: tuple[str, ...]
    interpretation_blockers: tuple[str, ...]
    confidence_improvers: tuple[str, ...]
    highlights: tuple[str, ...]
    findings: tuple[InvestigationFinding, ...]
    observations: tuple[InvestigationObservation, ...]
    observation_counts: tuple[tuple[str, int], ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "what_happened": self.what_happened,
            "is_complete": self.is_complete,
            "is_interpretable": self.is_interpretable,
            "completeness_gaps": list(self.completeness_gaps),
            "interpretation_blockers": list(self.interpretation_blockers),
            "confidence_improvers": list(self.confidence_improvers),
            "highlights": list(self.highlights),
            "findings": [finding.to_dict() for finding in self.findings],
            "observations": [observation.to_dict() for observation in self.observations],
            "observation_counts": dict(self.observation_counts),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ExperimentBriefSection:
    """Immutable report-preview section derived from one Investigator finding."""

    heading: str
    summary: str
    details: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "summary": self.summary,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class ExperimentBriefIdentity:
    """Deeply immutable experiment header for report previews."""

    experiment_id: str
    label: str
    technique: str | None
    instrument: str | None
    measurement_count: int
    observation_count: int
    observation_categories: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observation_categories"] = dict(self.observation_categories)
        return payload


@dataclass(frozen=True)
class ExperimentBriefPreview:
    """Versioned experiment-first brief without presentation or export concerns."""

    experiment: ExperimentBriefIdentity
    summary: str
    is_complete: bool
    is_interpretable: bool
    sections: tuple[ExperimentBriefSection, ...]
    observations: tuple[InvestigationObservation, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment.to_dict(),
            "summary": self.summary,
            "is_complete": self.is_complete,
            "is_interpretable": self.is_interpretable,
            "sections": [section.to_dict() for section in self.sections],
            "observations": [observation.to_dict() for observation in self.observations],
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ScientificContextItem:
    """Immutable local-memory item with stable retrieval provenance."""

    item_id: str
    layer: str
    entity_type: str
    title: str
    text: str
    experiment_id: str | None
    project_id: str | None
    instrument_id: str | None
    source_id: str | None
    tags: tuple[str, ...]
    confidence: str
    created_at: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True)
class RelatedScientificContext:
    """Versioned deterministic context packet for application clients."""

    question: str
    relevant_experiments: tuple[ScientificContextItem, ...]
    relevant_observations: tuple[ScientificContextItem, ...]
    supporting_evidence: tuple[ScientificContextItem, ...]
    hypotheses: tuple[ScientificContextItem, ...]
    recommendations: tuple[ScientificContextItem, ...]
    related_notes: tuple[ScientificContextItem, ...]
    source_files: tuple[ScientificContextItem, ...]
    missing_information: tuple[str, ...]
    confidence: str
    caveats: tuple[str, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "relevant_experiments": [item.to_dict() for item in self.relevant_experiments],
            "relevant_observations": [item.to_dict() for item in self.relevant_observations],
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "recommendations": [item.to_dict() for item in self.recommendations],
            "related_notes": [item.to_dict() for item in self.related_notes],
            "source_files": [item.to_dict() for item in self.source_files],
            "missing_information": list(self.missing_information),
            "confidence": self.confidence,
            "caveats": list(self.caveats),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ResearchJournalEntryRead:
    """Immutable grouped Research Journal entry."""

    entry_id: str
    created_at: str
    title: str
    experiment_id: str | None
    instrument: str | None
    tags: tuple[str, ...]
    samples: tuple[str, ...]
    key_observations: tuple[str, ...]
    hypotheses: tuple[str, ...]
    recommendations: tuple[str, ...]
    source_files: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "tags", "samples", "key_observations", "hypotheses",
            "recommendations", "source_files", "notes",
        ):
            payload[key] = list(payload[key])
        return payload


@dataclass(frozen=True)
class ResearchJournalRead:
    """Versioned filtered journal entries with the matching Markdown export."""

    keyword: str
    tag: str
    instrument: str
    sample: str
    entries: tuple[ResearchJournalEntryRead, ...]
    markdown: str
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "tag": self.tag,
            "instrument": self.instrument,
            "sample": self.sample,
            "entries": [entry.to_dict() for entry in self.entries],
            "markdown": self.markdown,
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ScientificNoteReceipt:
    """Immutable receipt for one explicitly requested local scientific note."""

    item_id: str
    title: str
    instrument_id: str | None
    tags: tuple[str, ...]
    confidence: str
    created_at: str | None
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "instrument_id": self.instrument_id,
            "tags": list(self.tags),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class ExperimentSaveReceipt:
    """Immutable metadata for one append-only experiment-history write."""

    record_id: str
    saved_at: str
    label: str
    measurement_count: int
    loaded_from_record_id: str | None = None
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityContract:
    """Discoverable application operation shared by all future interfaces.

    The registry describes in-process Python entry points. It deliberately does
    not define HTTP routing, authentication, serialization, or agent behavior.
    """

    name: str
    purpose: str
    handler: Callable[..., Any] = field(repr=False, compare=False)
    caller_types: tuple[str, ...] = ("Human UI", "Agent", "CLI", "Future API")
    version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return transport-neutral metadata without exposing the handler."""

        return {
            "name": self.name,
            "purpose": self.purpose,
            "caller_types": list(self.caller_types),
            "version": self.version,
        }


def agent_access_policy() -> AgentAccessPolicy:
    """Return the current planned access contract for future agents."""

    return AgentAccessPolicy()


def build_experiment_snapshot(experiment: Experiment) -> ExperimentSnapshot:
    """Build a stable, low-detail summary from an Experiment.

    The snapshot deliberately excludes raw files, traces, and full measurement
    payloads. It is safe for app navigation, reports, and future agent context
    selection while keeping the authoritative scientific data in Experiment.
    """

    categories: dict[str, int] = {}
    for observation in experiment.observations:
        categories[observation.category] = categories.get(observation.category, 0) + 1

    return ExperimentSnapshot(
        experiment_id=experiment.experiment_id,
        label=experiment.label,
        technique=experiment.technique,
        instrument=experiment.instrument,
        measurement_count=len(experiment.measurements),
        observation_count=len(experiment.observations),
        observation_categories=categories,
    )


def investigate_experiment(experiment: Experiment) -> ExperimentInvestigation:
    """Run the Scientific Investigator and return immutable evidence-backed results."""

    report = investigate_domain_experiment(experiment)
    findings = tuple(
        InvestigationFinding(
            question=finding.question,
            answer=finding.answer,
            details=tuple(finding.details),
        )
        for finding in report.findings
    )
    observations = tuple(
        InvestigationObservation(
            label=observation.label,
            category=observation.category,
            evidence=observation.evidence,
            sample_name=observation.sample_name,
            severity=observation.severity,
            confidence=observation.confidence,
            source_type=observation.source_type,
            source_id=observation.source_id,
            recommendation=observation.recommendation,
        )
        for observation in experiment.observations
    )
    return ExperimentInvestigation(
        experiment_id=report.experiment_id,
        what_happened=report.what_happened,
        is_complete=report.is_complete,
        is_interpretable=report.is_interpretable,
        completeness_gaps=tuple(report.completeness_gaps),
        interpretation_blockers=tuple(report.interpretation_blockers),
        confidence_improvers=tuple(report.confidence_improvers),
        highlights=tuple(report.highlights),
        findings=findings,
        observations=observations,
        observation_counts=tuple(report.observation_counts.items()),
    )


def produce_experiment_brief(experiment: Experiment) -> ExperimentBriefPreview:
    """Compose a stable report preview from an Experiment and Investigator result."""

    if not isinstance(experiment, Experiment):
        raise TypeError("Experiment brief input must be an Experiment")
    investigation = investigate_experiment(experiment)
    snapshot = build_experiment_snapshot(experiment)
    return ExperimentBriefPreview(
        experiment=ExperimentBriefIdentity(
            experiment_id=snapshot.experiment_id,
            label=snapshot.label,
            technique=snapshot.technique,
            instrument=snapshot.instrument,
            measurement_count=snapshot.measurement_count,
            observation_count=snapshot.observation_count,
            observation_categories=tuple(snapshot.observation_categories.items()),
        ),
        summary=investigation.what_happened,
        is_complete=investigation.is_complete,
        is_interpretable=investigation.is_interpretable,
        sections=tuple(
            ExperimentBriefSection(
                heading=finding.question,
                summary=finding.answer,
                details=finding.details,
            )
            for finding in investigation.findings
        ),
        observations=investigation.observations,
    )


def retrieve_related_context(
    question: str,
    *,
    tags: tuple[str, ...] = (),
    limit: int = 6,
    knowledge_path: Path = DEFAULT_KNOWLEDGE_STORE_PATH,
    store: KnowledgeStore | None = None,
) -> RelatedScientificContext:
    """Retrieve compact local scientific context through the application boundary."""

    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("A context question is required")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    packet = ContextRetriever(store or KnowledgeStore(knowledge_path)).retrieve(
        normalized_question,
        tags=tags,
        limit=limit,
    )

    def items(values) -> tuple[ScientificContextItem, ...]:
        return tuple(
            ScientificContextItem(
                item_id=item.item_id,
                layer=item.layer,
                entity_type=item.entity_type,
                title=item.title,
                text=item.text,
                experiment_id=item.experiment_id,
                project_id=item.project_id,
                instrument_id=item.instrument_id,
                source_id=item.source_id,
                tags=tuple(item.tags),
                confidence=item.confidence,
                created_at=item.created_at,
            )
            for item in values
        )

    return RelatedScientificContext(
        question=packet.question,
        relevant_experiments=items(packet.relevant_experiments),
        relevant_observations=items(packet.relevant_observations),
        supporting_evidence=items(packet.supporting_evidence),
        hypotheses=items(packet.hypotheses),
        recommendations=items(packet.recommendations),
        related_notes=items(packet.related_notes),
        source_files=items(packet.source_files),
        missing_information=tuple(packet.missing_information),
        confidence=packet.confidence,
        caveats=tuple(packet.caveats),
    )


def retrieve_research_journal(
    *,
    keyword: str = "",
    tag: str = "",
    instrument: str = "",
    sample: str = "",
    knowledge_path: Path = DEFAULT_KNOWLEDGE_STORE_PATH,
    store: KnowledgeStore | None = None,
) -> ResearchJournalRead:
    """Return filtered journal entries and their established Markdown export."""

    filters = {
        "keyword": keyword,
        "tag": tag,
        "instrument": instrument,
        "sample": sample,
    }
    journal = ResearchJournal(store or KnowledgeStore(knowledge_path))
    entries = journal.entries(**filters)
    read_entries = tuple(
        ResearchJournalEntryRead(
            entry_id=entry.entry_id,
            created_at=entry.created_at,
            title=entry.title,
            experiment_id=entry.experiment_id,
            instrument=entry.instrument,
            tags=tuple(entry.tags),
            samples=tuple(entry.samples),
            key_observations=tuple(entry.key_observations),
            hypotheses=tuple(entry.hypotheses),
            recommendations=tuple(entry.recommendations),
            source_files=tuple(entry.source_files),
            notes=tuple(entry.notes),
        )
        for entry in entries
    )
    return ResearchJournalRead(
        **filters,
        entries=read_entries,
        markdown=journal.export_markdown(**filters),
    )


def add_scientific_note(
    text: str,
    *,
    title: str = "",
    instrument_id: str | None = None,
    tags: tuple[str, ...] = (),
    knowledge_path: Path = DEFAULT_KNOWLEDGE_STORE_PATH,
    store: KnowledgeStore | None = None,
) -> ScientificNoteReceipt:
    """Persist one explicitly requested human note and return its receipt."""

    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Scientific note text is required")
    normalized_title = title.strip() or "Research note"
    normalized_instrument = (instrument_id or "").strip() or None
    normalized_tags = tuple(tag.strip() for tag in tags if tag.strip())
    item = (store or KnowledgeStore(knowledge_path)).add_note(
        normalized_text,
        title=normalized_title,
        instrument_id=normalized_instrument,
        tags=normalized_tags,
    )
    return ScientificNoteReceipt(
        item_id=item.item_id,
        title=item.title,
        instrument_id=item.instrument_id,
        tags=tuple(item.tags),
        confidence=item.confidence,
        created_at=item.created_at,
    )


def save_experiment_history(
    measurements: list[object],
    label: str = "",
    *,
    loaded_from_record_id: str | None = None,
    loaded_from_label: str | None = None,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> ExperimentSaveReceipt:
    """Append reviewed experiment evidence to local history and return a receipt."""

    if not measurements:
        raise ValueError("At least one measurement is required to save an experiment")
    if any(not callable(getattr(measurement, "to_dict", None)) for measurement in measurements):
        raise TypeError("Every saved measurement must provide to_dict() evidence")

    normalized_record_id = (loaded_from_record_id or "").strip() or None
    normalized_loaded_label = (loaded_from_label or "").strip() or None
    evidence = deepcopy(measurements)
    if normalized_record_id:
        lineage = {
            "loaded_from_record_id": normalized_record_id,
            "loaded_from_label": normalized_loaded_label,
            "save_semantics": "append_new_version",
        }
        for measurement in evidence:
            if isinstance(getattr(measurement, "provenance", None), dict):
                measurement.provenance["history_lineage"] = dict(lineage)
            elif isinstance(getattr(measurement, "metadata", None), dict):
                measurement.metadata["history_lineage"] = dict(lineage)

    record = save_history_experiment(evidence, label.strip(), history_path=history_path)
    return ExperimentSaveReceipt(
        record_id=record.id,
        saved_at=record.saved_at,
        label=record.label,
        measurement_count=len(evidence),
        loaded_from_record_id=normalized_record_id,
    )


def retrieve_experiment(
    record_id: str,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> RetrievedExperiment:
    """Retrieve one persisted experiment through the application boundary."""

    record = load_experiment_record(record_id, history_path=history_path)
    measurements = tuple(measurements_from_record(record))
    return RetrievedExperiment(
        record_id=record.id,
        saved_at=record.saved_at,
        label=record.label,
        measurement_count=len(measurements),
        _measurements=measurements,
    )


def list_experiments(
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> tuple[ExperimentListing, ...]:
    """List persisted experiments newest-first through the application boundary.

    The listing is tolerant: malformed JSONL lines are skipped by the underlying
    history reader so a single damaged record cannot hide the rest of the
    timeline. Ordering matches ``latest_experiment`` — newest ``saved_at`` first,
    with append order breaking same-second ties so the most recently saved record
    sorts first. Only immutable metadata is returned; measurements stay in
    persistence until a caller restores them by ``record_id``.
    """

    records = load_history(history_path)
    ordered = sorted(
        enumerate(records),
        key=lambda item: (item[1].saved_at, item[0]),
        reverse=True,
    )
    return tuple(
        ExperimentListing(
            record_id=record.id,
            saved_at=record.saved_at,
            label=record.label,
            measurement_count=len(record.measurements),
        )
        for _, record in ordered
    )


def compare_experiments(
    current: list[Measurement],
    *,
    baseline_record_id: str | None = None,
    exclude_record_id: str | None = None,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> ExperimentComparison:
    """Compare current DLS evidence with a selected or latest saved run.

    Sample matching and drift thresholds remain owned by ``history``. This
    application query selects the baseline and translates the DataFrame into a
    stable immutable read contract suitable for any shell.
    """

    if baseline_record_id is not None:
        baseline = load_experiment_record(baseline_record_id, history_path=history_path)
    else:
        baseline = latest_experiment(load_history(history_path), exclude_id=exclude_record_id)

    table = compare_history_experiments(current, baseline)
    rows = tuple(
        ExperimentComparisonRow(
            sample_name=row["Sample"],
            z_average_nm=row["Z-Average"],
            previous_z_average_nm=row["Previous Z-Average"],
            z_change_percent=row["Z Change %"],
            pdi=row["PDI"],
            previous_pdi=row["Previous PDI"],
            pdi_change=row["PDI Change"],
            drift=row["Drift"],
        )
        for row in table.to_dict(orient="records")
    )
    return ExperimentComparison(
        baseline_record_id=baseline.id if baseline else None,
        baseline_label=baseline.label if baseline else None,
        baseline_saved_at=baseline.saved_at if baseline else None,
        rows=rows,
        drifted_sample_count=sum("drift" in row.drift.lower() for row in rows),
    )


def retrieve_history_overview(
    *, history_path: Path = DEFAULT_HISTORY_PATH
) -> HistoryOverview:
    """Return persisted summary and trend evidence without exposing storage."""

    records = load_history(history_path)
    summaries = tuple(
        HistorySummary(
            record_id=row["Record ID"],
            saved_at=row["Saved At"],
            experiment_label=row["Experiment"],
            measurement_count=row["Measurements"],
            flagged_count=row["Flagged"],
            review_count=row["Review"],
            median_z_average_nm=row["Median Z-Average"],
            median_pdi=row["Median PDI"],
        )
        for row in history_table(records).to_dict(orient="records")
    )
    points = tuple(
        HistoryTrendPoint(
            saved_at=row["Saved At"],
            experiment_label=row["Experiment"],
            sample_name=row["Sample"],
            z_average_nm=row["Z-Average"],
            pdi=row["PDI"],
            status=row["Status"],
        )
        for row in trend_table(records).to_dict(orient="records")
    )
    return HistoryOverview(summaries=summaries, trend_points=points)


def find_related_experiments(
    measurement: Measurement,
    *,
    top_n: int = 5,
    exclude_record_id: str | None = None,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> RelatedExperiments:
    """Find the nearest saved DLS samples through the application boundary.

    Ranking, feature weighting, and the readability score remain owned by the
    history layer. The score expresses relative feature proximity, not a
    probability or a causal scientific relationship.
    """

    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    table = find_similar_samples(
        measurement,
        load_history(history_path),
        top_n=top_n,
        exclude_id=exclude_record_id,
    )
    matches = tuple(
        RelatedExperimentMatch(
            experiment_label=row["Experiment"],
            saved_at=row["Saved At"],
            sample_name=row["Sample"],
            z_average_nm=row["Z-Average"],
            pdi=row["PDI"],
            primary_peak_nm=row["Primary Peak"],
            distance=row["Distance"],
            similarity_score=row["Similarity"],
        )
        for row in table.to_dict(orient="records")
    )
    return RelatedExperiments(
        query_sample_name=measurement.metadata.sample_name,
        matches=matches,
    )


def generate_observations(
    evidence: list[object],
    *,
    technique: str,
    assessment: MassBalanceAssessment | None = None,
) -> ObservationGenerationResult:
    """Normalize supported technique evidence through authoritative domain helpers."""

    if not evidence:
        raise ValueError("At least one evidence item is required to generate observations")
    normalized_technique = technique.strip().lower()
    if normalized_technique == "dls":
        if assessment is not None:
            raise ValueError("DLS observation generation does not accept an assessment")
        if any(not hasattr(item, "measurement") or not hasattr(item, "warnings") for item in evidence):
            raise TypeError("DLS observation evidence must contain parsed samples")
        observations = observations_from_samples(evidence)
        public_technique = "DLS"
    elif normalized_technique in {"chromatography", "hplc", "sec"}:
        if assessment is None:
            raise ValueError("Chromatography observation generation requires a mass-balance assessment")
        if any(not isinstance(item, ChromatographyMeasurement) for item in evidence):
            raise TypeError("Chromatography observation evidence must contain chromatography measurements")
        assessment_evidence = deepcopy(assessment)
        assessment_evidence.observations = observations_from_mass_balance_assessment(
            assessment_evidence
        )
        observations = chromatography_observations(evidence, assessment_evidence)
        public_technique = "Chromatography"
    elif normalized_technique == "filtration":
        if assessment is not None:
            raise ValueError("Filtration observation generation does not accept an assessment")
        if any(not isinstance(item, FiltrationMeasurement) for item in evidence):
            raise TypeError("Filtration observation evidence must contain filtration measurements")
        observations = [
            observation
            for measurement in evidence
            for observation in observations_from_filtration_measurement(measurement)
        ]
        public_technique = "Filtration"
    else:
        raise ValueError(f"Unsupported observation technique: {technique}")

    domain_observations = tuple(deepcopy(observations))
    return ObservationGenerationResult(
        technique=public_technique,
        observations=tuple(
            ObservationRead(
                label=observation.label,
                category=observation.category,
                evidence=observation.evidence,
                sample_name=observation.sample_name,
                severity=observation.severity,
                confidence=observation.confidence,
                source_type=observation.source_type,
                source_id=observation.source_id,
                recommendation=observation.recommendation,
            )
            for observation in domain_observations
        ),
        _domain_observations=domain_observations,
    )


def dls_experiment_from_samples(
    samples: list[Any],
    *,
    label: str = "",
    source_files: list[str] | None = None,
) -> Experiment:
    """Create a DLS Experiment from parsed UI/import samples.

    This is an application operation rather than a Streamlit operation. The UI,
    future API handlers, and future agent SDK can all call the same boundary.
    """

    observations = generate_observations(samples, technique="DLS").restore_observations()
    experiment_label = label.strip() or "DLS experiment"
    metadata = {
        "sample_count": len(samples),
        "source_files": list(source_files or []),
    }
    return Experiment(
        experiment_id=uuid4().hex,
        label=experiment_label,
        instrument="DLS",
        technique="DLS",
        source_path=None,
        created_at=_utc_now(),
        measurements=[sample.measurement for sample in samples],
        observations=observations,
        metadata=metadata,
    )


def analyze_dls_uploads(sources: list[object]) -> DLSUploadImportResult:
    """Classify and import seekable uploaded DLS sources without a UI dependency."""

    if not sources:
        raise ValueError("Select at least one uploaded DLS file.")
    if any(not isinstance(getattr(source, "name", None), str) for source in sources):
        raise TypeError("Every uploaded DLS source must provide a file name")
    if any(not callable(getattr(source, "read", None)) for source in sources):
        raise TypeError("Every uploaded DLS source must be readable")

    preview = build_import_preview(sources)
    file_read_cache: dict[int, DLSUploadFileRead] = {}

    def file_read(classified) -> DLSUploadFileRead:
        key = id(classified)
        if key not in file_read_cache:
            parsed_source = (
                classified.parsed_result.source_text
                if classified.parsed_result is not None
                else ""
            )
            file_read_cache[key] = DLSUploadFileRead(
                file_name=classified.file_name,
                file_type=classified.file_type,
                source_text=classified.source_text or parsed_source,
                error=classified.error,
            )
        return file_read_cache[key]

    groups = tuple(
        DLSUploadGroupRead(
            lot=group.lot,
            status=group.status,
            summary_files=tuple(file_read(item) for item in group.summary_files),
            intensity_files=tuple(file_read(item) for item in group.intensity_files),
            correlogram_files=tuple(file_read(item) for item in group.correlogram_files),
            files=tuple(file_read(item) for item in group.files),
        )
        for group in preview.groups
    )
    try:
        imports = import_measurement_groups(preview.groups)
        measurements = [result.measurement for result in imports if result.measurement is not None]
        errors = [error for result in imports for error in result.errors]
        samples = [sample_from_measurement(measurement) for measurement in measurements]
    except Exception as error:  # preserve the existing resilient upload workflow
        samples = []
        errors = [f"Import failed: {error}"]

    frozen_samples = tuple(deepcopy(samples))
    return DLSUploadImportResult(
        groups=groups,
        measurements=_dls_measurement_summaries(samples),
        source_files=tuple(source.name for source in sources),
        import_errors=tuple(errors),
        _samples=frozen_samples,
    )


def rank_dls_decisions(samples: list[Any]) -> DLSDecisionRanking:
    """Apply the established DLS screening rank and return immutable rows."""

    if not samples:
        raise ValueError("At least one parsed DLS sample is required for decision ranking")
    if any(
        not hasattr(sample, "name")
        or not hasattr(sample, "metrics")
        or not hasattr(sample, "warnings")
        for sample in samples
    ):
        raise TypeError("DLS decision ranking requires parsed samples")

    decision = build_decision_brief(samples, build_metrics_table(samples))
    attention_rows = tuple(
        DLSAttentionRow(
            sample_name=str(row["Sample"]),
            status=str(row["Status"]),
            attention_score=float(row["Attention Score"]),
            reason=str(row["Reason"]),
            warnings=str(row["Warnings"]),
        )
        for row in decision["attention"].to_dict(orient="records")
    )
    return DLSDecisionRanking(
        best_candidate=str(decision["best"]),
        attention_candidate=str(decision["worst"]),
        flagged_count=sum(row.status != STATUS_NORMAL for row in attention_rows),
        sample_count=len(samples),
        review_samples=str(decision["review"]),
        next_check=str(decision["next_check"]),
        unusual_changes=tuple(str(item) for item in decision["unusual"]),
        attention_rows=attention_rows,
    )


def compose_dls_narrative(samples: list[Any]) -> DLSNarrative:
    """Compose established rule-based DLS findings and trend text once."""

    if not samples:
        raise ValueError("At least one parsed DLS sample is required for narrative composition")
    if any(
        not hasattr(sample, "name")
        or not hasattr(sample, "metrics")
        or not hasattr(sample, "warnings")
        for sample in samples
    ):
        raise TypeError("DLS narrative composition requires parsed samples")

    metrics = build_metrics_table(samples)

    def freeze(sections: dict[str, list[str]]) -> tuple[DLSNarrativeSection, ...]:
        return tuple(
            DLSNarrativeSection(
                heading=str(heading),
                bullets=tuple(str(item) for item in items),
            )
            for heading, items in sections.items()
        )

    return DLSNarrative(
        automated_findings=freeze(build_ai_summary(samples, metrics)),
        data_story=freeze(build_data_story(samples, metrics)),
        detailed_analysis=freeze(build_data_analysis(samples, metrics)),
    )


def summarize_dls_health(samples: list[Any]) -> DLSHealthOverview:
    """Return the established DLS screening score, counts, and medians."""

    if not samples:
        raise ValueError("At least one parsed DLS sample is required for health summary")
    if any(
        not hasattr(sample, "name")
        or not hasattr(sample, "metrics")
        or not hasattr(sample, "warnings")
        for sample in samples
    ):
        raise TypeError("DLS health summary requires parsed samples")

    statuses = tuple(sample_status(sample) for sample in samples)
    status_weights = {
        STATUS_NORMAL: 100,
        STATUS_WATCH: 65,
        STATUS_REVIEW: 25,
    }
    metrics = build_metrics_table(samples)
    z_values = metrics["Z-Average"].dropna()
    tail_values = metrics["Tail Index"].dropna()

    return DLSHealthOverview(
        screening_score=int(
            round(sum(status_weights.get(status, 50) for status in statuses) / len(statuses))
        ),
        sample_count=len(samples),
        flagged_count=sum(status != STATUS_NORMAL for status in statuses),
        review_count=sum(status == STATUS_REVIEW for status in statuses),
        median_z_average_nm=float(z_values.median()) if not z_values.empty else None,
        median_tail_percent=float(tail_values.median()) if not tail_values.empty else None,
    )


def analyze_dls_trend_diagnostics(samples: list[Any]) -> DLSTrendDiagnostics:
    """Return established DLS control-chart and replicate statistics as rows."""

    if not samples:
        raise ValueError("At least one parsed DLS sample is required for trend diagnostics")
    if any(
        not hasattr(sample, "name")
        or not hasattr(sample, "metrics")
        or not hasattr(sample, "measurement")
        for sample in samples
    ):
        raise TypeError("DLS trend diagnostics require parsed samples")

    metrics = build_metrics_table(samples)
    control_rows = tuple(
        DLSControlChartRow(
            sample_name=str(row["Sample"]),
            metric=str(row["Metric"]),
            value=float(row["Value"]),
            mean=float(row["Mean"]),
            warning_low=float(row["Warning Low"]),
            warning_high=float(row["Warning High"]),
            action_low=float(row["Action Low"]),
            action_high=float(row["Action High"]),
            zone=str(row["Zone"]),
        )
        for row in control_chart_table(samples, metrics).to_dict(orient="records")
    )
    replicate_rows = tuple(
        DLSReplicateStatisticsRow(
            sample_name=str(row["Sample"]),
            metric=str(row["Metric"]),
            count=int(row["N"]),
            mean=float(row["Mean"]) if row["Mean"] is not None else None,
            standard_deviation=float(row["SD"]) if row["SD"] is not None else None,
            relative_standard_deviation_percent=(
                float(row["%RSD"]) if row["%RSD"] is not None else None
            ),
            drift=str(row["Drift"]),
            outliers=str(row["Outliers"]),
            change_point=str(row["Change Point"]),
        )
        for row in replicate_statistics_table(samples).to_dict(orient="records")
    )
    return DLSTrendDiagnostics(
        control_chart_rows=control_rows,
        replicate_statistics_rows=replicate_rows,
    )


def analyze_dls_dataset(
    paths: list[str | Path],
    *,
    label: str = "",
) -> DLSAnalysisResult:
    """Import and analyze an existing local DLS dataset.

    This application operation owns file opening, multi-file grouping,
    measurement assembly, observation generation, and read-model creation so
    desktop and future shells do not reproduce the scientific workflow.
    """
    source_paths = [Path(path).expanduser() for path in paths]
    if not source_paths:
        raise ValueError("Select at least one DLS file.")
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"DLS file not found: {missing[0]}")

    opened_files = []
    try:
        for path in source_paths:
            opened_files.append(path.open("rb"))
        preview = build_import_preview(opened_files)
        supported_groups = [group for group in preview.groups if group.summary_files or group.intensity_files]
        if not supported_groups:
            raise ValueError("No supported DLS summary or intensity distribution files were found.")
        imports = import_measurement_groups(supported_groups)
    finally:
        for opened_file in opened_files:
            opened_file.close()

    measurements = [result.measurement for result in imports if result.measurement is not None]
    if not measurements:
        errors = [error for result in imports for error in result.errors]
        detail = errors[0] if errors else "No supported DLS measurements were found."
        raise ValueError(detail)

    samples = [sample_from_measurement(measurement) for measurement in measurements]
    source_files = [str(path) for path in source_paths]
    experiment = dls_experiment_from_samples(samples, label=label, source_files=source_files)
    return DLSAnalysisResult(
        experiment=build_experiment_snapshot(experiment),
        measurements=_dls_measurement_summaries(samples),
        source_files=tuple(source_files),
        import_errors=tuple(error for result in imports for error in result.errors),
    )


def restore_dls_experiment(
    record_id: str,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> DLSAnalysisResult:
    """Restore a persisted DLS experiment as a read-only analysis result.

    This reuses the persisted-retrieval capability (``retrieve_experiment``) and
    the shared DLS summary assembly so desktop and future shells never read JSONL
    storage directly or recompute scientific metrics. The returned result mirrors
    ``analyze_dls_dataset`` so a restored record renders through the same read
    model as a freshly imported dataset.
    """

    retrieved = retrieve_experiment(record_id, history_path=history_path)
    measurements = retrieved.restore_measurements()
    samples = [sample_from_measurement(measurement) for measurement in measurements]
    source_files = list(
        dict.fromkeys(
            source
            for sample in samples
            for source in sample.measurement.metadata.source_files
        )
    )
    experiment = dls_experiment_from_samples(
        samples, label=retrieved.label, source_files=source_files
    )
    return DLSAnalysisResult(
        experiment=build_experiment_snapshot(experiment),
        measurements=_dls_measurement_summaries(samples),
        source_files=tuple(source_files),
        import_errors=(),
    )


def _dls_measurement_summaries(samples: list[Any]) -> tuple[DLSMeasurementSummary, ...]:
    """Build immutable per-lot read summaries shared by import and restore."""

    return tuple(
        DLSMeasurementSummary(
            sample_name=sample.name,
            status=sample_status(sample),
            source_files=tuple(sample.measurement.metadata.source_files),
            z_average_nm=sample.measurement.summary_metrics.z_average,
            pdi=sample.measurement.summary_metrics.pdi,
            primary_peak_nm=sample.measurement.derived_metrics.primary_peak_nm,
            d50_nm=sample.measurement.derived_metrics.d50_nm,
            aggregation_risk=sample.measurement.derived_metrics.aggregation_risk,
            quality_score=sample.measurement.derived_metrics.quality_score,
            warnings=tuple(sample.warnings),
        )
        for sample in samples
    )


def restore_chromatography_experiment(
    record_id: str,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> ChromatographyRestoreResult:
    """Restore persisted chromatography evidence into a stable read model."""

    record = load_experiment_record(record_id, history_path=history_path)
    measurements = chromatography_measurements_from_record(record)
    assessment = assess_chromatography_mass_balance(measurements)
    observations = generate_observations(
        measurements, technique="Chromatography", assessment=assessment
    ).restore_observations()
    hypotheses = mass_balance_hypotheses(observations)
    assessment.hypotheses = list(hypotheses)
    source_files = tuple(
        dict.fromkeys(source for measurement in measurements for source in measurement.source_files)
    )
    experiment = chromatography_experiment_from_preview(
        {
            "measurements": measurements,
            "assessment": assessment,
            "observations": observations,
            "hypotheses": hypotheses,
        },
        label=record.label,
        source_name=source_files[0] if len(source_files) == 1 else None,
    )
    summaries = tuple(
        ChromatographyMeasurementSummary(
            sample_name=measurement.sample_name,
            technique=measurement.technique,
            timepoint=measurement.timepoint,
            injection_id=measurement.injection_id,
            method_name=measurement.method_name,
            replicate_id=measurement.replicate_id,
            source_files=tuple(measurement.source_files),
            peak_count=len(measurement.peaks),
            chromatogram_trace_count=len(measurement.chromatogram_traces),
            total_area=measurement.total_area,
            parent_peak_id=measurement.parent_peak_id,
            signal_file_count=len(measurement.metadata.get("openlab_signal_files", [])),
            raw_data_file=measurement.metadata.get("raw_data_file"),
            acquired_at=measurement.metadata.get("measurement_datetime"),
        )
        for measurement in measurements
    )
    return ChromatographyRestoreResult(
        record_id=record.id,
        saved_at=record.saved_at,
        experiment=build_experiment_snapshot(experiment),
        measurements=summaries,
        source_files=source_files,
        hypotheses=tuple(hypotheses),
    )


def chromatography_experiment_from_preview(
    preview: dict[str, Any],
    *,
    label: str = "",
    source_name: str | None = None,
) -> Experiment:
    """Create an HPLC Experiment from a chromatography import preview."""

    if "openlab_experiment" in preview:
        experiment = preview["openlab_experiment"]
        if label.strip():
            experiment.label = label.strip()
        if source_name:
            experiment.source_path = source_name
            experiment.metadata["source_name"] = source_name
        return experiment

    observations = list(preview.get("observations") or [])
    hypotheses = list(preview.get("hypotheses") or [])
    assessment = preview.get("assessment")
    experiment_label = label.strip() or "Chromatography experiment"
    unsupported_sections = []
    if not any(observation.label == "Peak table available" for observation in observations):
        unsupported_sections.append("Chromatography CSV import does not include raw detector signal traces.")
    return Experiment(
        experiment_id=uuid4().hex,
        label=experiment_label,
        instrument="Chromatography",
        technique="HPLC",
        source_path=source_name,
        created_at=_utc_now(),
        measurements=list(preview.get("measurements") or []),
        observations=observations,
        unsupported_sections=unsupported_sections,
        metadata={
            "source_name": source_name,
            "hypotheses": hypotheses,
            "assessment": assessment.to_dict() if hasattr(assessment, "to_dict") else {},
        },
    )


def analyze_chromatography_source(
    source: Any,
    *,
    label: str = "Chromatography preview",
    source_name: str | None = None,
) -> ChromatographyAnalysisResult:
    """Import and analyze chromatography CSV or OpenLab evidence outside a UI."""

    resolved_name = source_name or getattr(source, "name", None) or str(source)
    suffix = Path(str(resolved_name)).suffix.lower()
    if suffix not in {".csv", ".olax"}:
        raise ValueError("Chromatography source must be a CSV or OpenLab .olax file")

    assessment = None
    trends: tuple[ChromatographyTrendPoint, ...] = ()
    hypotheses: tuple[str, ...] = ()
    if suffix == ".olax":
        if isinstance(source, (str, Path)):
            experiment = build_experiment_from_olax(source, label=Path(resolved_name).name)
        else:
            source.seek(0)
            with tempfile.NamedTemporaryFile(suffix=".olax") as temporary:
                temporary.write(source.read())
                temporary.flush()
                experiment = build_experiment_from_olax(
                    temporary.name, label=Path(resolved_name).name
                )
        experiment.label = label.strip() or experiment.label
        experiment.source_path = str(resolved_name)
        experiment.metadata["source_name"] = str(resolved_name)
        source_kind = "openlab_olax"
    else:
        measurements = parse_chromatography_csv(source)
        domain_assessment = assess_chromatography_mass_balance(measurements)
        observations = generate_observations(
            measurements,
            technique="Chromatography",
            assessment=domain_assessment,
        ).restore_observations()
        hypotheses = tuple(mass_balance_hypotheses(observations))
        domain_assessment.hypotheses = list(hypotheses)
        experiment = chromatography_experiment_from_preview(
            {
                "measurements": measurements,
                "assessment": domain_assessment,
                "observations": observations,
                "hypotheses": hypotheses,
            },
            label=label,
            source_name=str(resolved_name),
        )
        assessment = ChromatographyAssessmentRead(
            sample_name=domain_assessment.sample_name,
            parent_area_percent=domain_assessment.parent_area_percent,
            known_impurity_area_percent=domain_assessment.known_impurity_area_percent,
            unknown_area_percent=domain_assessment.unknown_area_percent,
            total_area_change_percent=domain_assessment.total_area_change_percent,
            replicate_rsd_percent=domain_assessment.replicate_rsd_percent,
        )
        peak_rows = peak_area_trend_table(measurements).to_dict(orient="records")
        total_rows = {
            row["Timepoint"]: row
            for row in total_area_trend_table(measurements).to_dict(orient="records")
        }
        trends = tuple(
            ChromatographyTrendPoint(
                timepoint=row["Timepoint"],
                parent_area_percent=row["Parent Area %"],
                known_impurity_area_percent=row["Known Impurity Area %"],
                unknown_area_percent=row["Unknown Area %"],
                total_area=row["Total Area"],
                parent_retention_time_min=row["Parent RT (min)"],
                change_vs_start_percent=total_rows.get(row["Timepoint"], {}).get(
                    "Change vs Start %"
                ),
            )
            for row in peak_rows
        )
        source_kind = "chromatography_csv"

    metadata = experiment.metadata
    return ChromatographyAnalysisResult(
        source_kind=source_kind,
        source_name=str(resolved_name),
        experiment=build_experiment_snapshot(experiment),
        measurements=_chromatography_measurement_summaries(experiment.measurements),
        observations=tuple(
            InvestigationObservation(
                label=observation.label,
                category=observation.category,
                evidence=observation.evidence,
                sample_name=observation.sample_name,
                severity=observation.severity,
                confidence=observation.confidence,
                source_type=observation.source_type,
                source_id=observation.source_id,
                recommendation=observation.recommendation,
            )
            for observation in experiment.observations
        ),
        hypotheses=hypotheses,
        unsupported_sections=tuple(experiment.unsupported_sections),
        assessment=assessment,
        trends=trends,
        source_summary=ChromatographySourceSummary(
            detector_file_count=len(metadata.get("detector_files", [])),
            peak_table_file_count=len(metadata.get("peak_table_files", [])),
            acquisition_method_file_count=len(metadata.get("acquisition_method_files", [])),
            audit_file_count=len(metadata.get("audit_files", [])),
        ),
        _experiment=deepcopy(experiment),
    )


def analyze_filtration_csv(
    source: Any,
    *,
    source_name: str | None = None,
) -> FiltrationImportRead:
    """Parse filtration CSV evidence into immutable application summaries."""

    resolved_name = source_name or getattr(source, "name", None)
    result = parse_filtration_csv(source, source_name=resolved_name)
    summaries = tuple(_filtration_measurement_summary(measurement) for measurement in result.measurements)
    return FiltrationImportRead(
        source_name=result.source_name,
        measurements=summaries,
        warnings=tuple(result.warnings),
        errors=tuple(result.errors),
        missing_columns=tuple(result.missing_columns),
        unsupported_columns=tuple(result.unsupported_columns),
        _measurements=tuple(deepcopy(result.measurements)),
    )


def _filtration_measurement_summary(
    measurement: FiltrationMeasurement,
) -> FiltrationMeasurementSummary:
    trace = measurement.trace
    trace_read = (
        FiltrationTraceRead(
            time_values=tuple(trace.time_values),
            time_unit=trace.time_unit,
            time_minutes=tuple(trace.time_minutes),
            pressure_values=tuple(trace.pressure_values),
            pressure_unit=trace.pressure_unit,
            pressure_kpa=tuple(trace.pressure_kpa),
            flow_rate_values=tuple(trace.flow_rate_values),
            flow_rate_unit=trace.flow_rate_unit,
        )
        if trace
        else None
    )
    return FiltrationMeasurementSummary(
        sample_name=measurement.sample_name,
        difficulty_score=measurement.difficulty_score,
        filtration_time_minutes=measurement.filtration_time_minutes,
        pressure=measurement.pressure,
        pressure_unit=measurement.pressure_unit,
        pressure_kpa=measurement.pressure_kpa,
        filter_type=measurement.filter_type,
        clogging_observed=measurement.clogging_observed,
        notes=measurement.notes,
        source=measurement.source,
        source_file=measurement.source_file,
        warnings=tuple(measurement.warnings),
        trace=trace_read,
    )


def _chromatography_measurement_summaries(
    measurements: list[Any],
) -> tuple[ChromatographyMeasurementSummary, ...]:
    return tuple(
        ChromatographyMeasurementSummary(
            sample_name=measurement.sample_name,
            technique=measurement.technique,
            timepoint=measurement.timepoint,
            injection_id=measurement.injection_id,
            method_name=measurement.method_name,
            replicate_id=measurement.replicate_id,
            source_files=tuple(measurement.source_files),
            peak_count=len(measurement.peaks),
            chromatogram_trace_count=len(measurement.chromatogram_traces),
            total_area=measurement.total_area,
            parent_peak_id=measurement.parent_peak_id,
            signal_file_count=len(measurement.metadata.get("openlab_signal_files", [])),
            raw_data_file=measurement.metadata.get("raw_data_file"),
            acquired_at=measurement.metadata.get("measurement_datetime"),
        )
        for measurement in measurements
    )


def save_experiment_to_memory(
    experiment: Experiment,
    *,
    human_note: str = "",
    project_id: str | None = None,
    tags: list[str] | None = None,
    store: KnowledgeStore | None = None,
) -> None:
    """Persist an Experiment and its scientific context to the knowledge store."""

    knowledge_store = store or KnowledgeStore()
    knowledge_store.add_experiment(experiment, project_id=project_id, tags=tags or [])
    for hypothesis in experiment.metadata.get("hypotheses", []):
        knowledge_store.add_hypothesis(
            str(hypothesis),
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "hypothesis"],
        )
    for recommendation in experiment.metadata.get("recommendations", []):
        knowledge_store.add_recommendation(
            str(recommendation),
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "recommendation"],
        )
    if human_note.strip():
        knowledge_store.add_note(
            human_note.strip(),
            title=f"Note: {experiment.label}",
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "human_note"],
        )


def app_manifest() -> dict[str, Any]:
    """Describe LabAssistant's current product boundary for app shells."""

    return {
        "name": APP_NAME,
        "direction": APP_DIRECTION,
        "primary_surface": HUMAN_APP_SURFACE,
        "agent_access": agent_access_policy().to_dict(),
        "capabilities": [capability.to_dict() for capability in list_capabilities()],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_CAPABILITY_REGISTRY: tuple[CapabilityContract, ...] = (
    CapabilityContract(
        name="describe_platform",
        purpose="Describe the LabAssistant product boundary and access policy.",
        handler=app_manifest,
    ),
    CapabilityContract(
        name="describe_agent_access",
        purpose="Describe the reviewed boundaries for future agent clients.",
        handler=agent_access_policy,
    ),
    CapabilityContract(
        name="import_dls_experiment",
        purpose="Assemble parsed DLS evidence into an experiment.",
        handler=dls_experiment_from_samples,
    ),
    CapabilityContract(
        name="analyze_dls_dataset",
        purpose="Import and analyze an existing local DLS dataset.",
        handler=analyze_dls_dataset,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="analyze_dls_uploads",
        purpose="Preview and import uploaded DLS evidence into immutable summaries.",
        handler=analyze_dls_uploads,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="rank_dls_decisions",
        purpose="Rank parsed DLS samples for deterministic screening attention.",
        handler=rank_dls_decisions,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="compose_dls_narrative",
        purpose="Compose deterministic DLS findings and trend narrative.",
        handler=compose_dls_narrative,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="summarize_dls_health",
        purpose="Summarize DLS screening health, status counts, and metric medians.",
        handler=summarize_dls_health,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="analyze_dls_trend_diagnostics",
        purpose="Return immutable DLS control-chart and replicate diagnostics.",
        handler=analyze_dls_trend_diagnostics,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="import_chromatography_experiment",
        purpose="Assemble a chromatography import preview into an experiment.",
        handler=chromatography_experiment_from_preview,
    ),
    CapabilityContract(
        name="analyze_chromatography_source",
        purpose="Import and analyze chromatography CSV or OpenLab evidence.",
        handler=analyze_chromatography_source,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="analyze_filtration_csv",
        purpose="Parse filtration CSV evidence into immutable summaries.",
        handler=analyze_filtration_csv,
        caller_types=("Human UI", "CLI", "Future API"),
    ),
    CapabilityContract(
        name="generate_observations",
        purpose="Normalize supported technique evidence into immutable findings.",
        handler=generate_observations,
    ),
    CapabilityContract(
        name="list_experiments",
        purpose="List persisted experiments newest-first for timeline browsing.",
        handler=list_experiments,
    ),
    CapabilityContract(
        name="compare_experiments",
        purpose="Explain meaningful DLS differences from a persisted experiment.",
        handler=compare_experiments,
    ),
    CapabilityContract(
        name="find_related_experiments",
        purpose="Rank saved DLS samples by feature similarity.",
        handler=find_related_experiments,
    ),
    CapabilityContract(
        name="retrieve_history_overview",
        purpose="Return persisted experiment summaries and sample trend evidence.",
        handler=retrieve_history_overview,
    ),
    CapabilityContract(
        name="retrieve_experiment",
        purpose="Load one persisted experiment with history provenance.",
        handler=retrieve_experiment,
    ),
    CapabilityContract(
        name="retrieve_experiment_summary",
        purpose="Return a stable read-only summary of an experiment.",
        handler=build_experiment_snapshot,
    ),
    CapabilityContract(
        name="investigate_experiment",
        purpose="Assess experiment completeness and interpretability from normalized observations.",
        handler=investigate_experiment,
    ),
    CapabilityContract(
        name="produce_experiment_brief",
        purpose="Compose an immutable experiment-level report preview.",
        handler=produce_experiment_brief,
    ),
    CapabilityContract(
        name="retrieve_related_context",
        purpose="Retrieve compact evidence-backed context from local scientific memory.",
        handler=retrieve_related_context,
    ),
    CapabilityContract(
        name="retrieve_research_journal",
        purpose="List and export filtered Research Journal entries.",
        handler=retrieve_research_journal,
    ),
    CapabilityContract(
        name="add_scientific_note",
        purpose="Persist one explicitly confirmed human scientific note.",
        handler=add_scientific_note,
        caller_types=("Human UI", "CLI"),
    ),
    CapabilityContract(
        name="save_experiment_history",
        purpose="Append explicitly confirmed experiment evidence to local history.",
        handler=save_experiment_history,
        caller_types=("Human UI", "CLI"),
    ),
    CapabilityContract(
        name="save_scientific_memory",
        purpose="Persist an experiment and its scientific context.",
        handler=save_experiment_to_memory,
    ),
)


def list_capabilities() -> tuple[CapabilityContract, ...]:
    """Return the stable, transport-independent capability catalog."""

    return _CAPABILITY_REGISTRY


def get_capability(name: str) -> CapabilityContract:
    """Resolve a capability contract by its stable public name."""

    for capability in _CAPABILITY_REGISTRY:
        if capability.name == name:
            return capability
    raise KeyError(f"Unknown LabAssistant capability: {name}")
