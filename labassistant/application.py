from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from labassistant.context_engine import KnowledgeStore
from labassistant.chromatography import mass_balance_hypotheses
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
    trend_table,
)
from labassistant.importers.chromatography import (
    assess_chromatography_mass_balance,
    chromatography_observations,
)
from labassistant.importers.measurement_importer import build_import_preview, import_measurement_groups
from labassistant.investigator import investigate as investigate_domain_experiment
from labassistant.models import Experiment, Measurement
from labassistant.observations import observations_from_samples
from labassistant.view_models import sample_from_measurement, sample_status


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
class ChromatographyMeasurementSummary:
    """Concise immutable summary of one persisted chromatography injection."""

    sample_name: str
    technique: str
    timepoint: str | None
    injection_id: str | None
    replicate_id: str | None
    source_files: tuple[str, ...]
    peak_count: int
    chromatogram_trace_count: int
    total_area: float | None
    parent_peak_id: str | None

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

    observations = observations_from_samples(samples)
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
    observations = chromatography_observations(measurements, assessment)
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
            replicate_id=measurement.replicate_id,
            source_files=tuple(measurement.source_files),
            peak_count=len(measurement.peaks),
            chromatogram_trace_count=len(measurement.chromatogram_traces),
            total_area=measurement.total_area,
            parent_peak_id=measurement.parent_peak_id,
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
        name="import_chromatography_experiment",
        purpose="Assemble a chromatography import preview into an experiment.",
        handler=chromatography_experiment_from_preview,
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
