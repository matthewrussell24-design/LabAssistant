from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from labassistant.context_engine import KnowledgeStore
from labassistant.history import DEFAULT_HISTORY_PATH, load_experiment_record, measurements_from_record
from labassistant.importers.measurement_importer import build_import_preview, import_measurement_groups
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
        imports = import_measurement_groups(preview.groups)
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
    summaries = tuple(
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
    return DLSAnalysisResult(
        experiment=build_experiment_snapshot(experiment),
        measurements=summaries,
        source_files=tuple(source_files),
        import_errors=tuple(error for result in imports for error in result.errors),
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
