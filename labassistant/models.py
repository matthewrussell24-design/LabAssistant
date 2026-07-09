from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MeasurementMetadata:
    sample_name: str
    source_files: list[str] = field(default_factory=list)
    measurement_datetime: str | None = None
    instrument: str | None = None
    operator: str | None = None
    temperature: str | None = None
    scattering_angle: str | None = None
    method: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class SummaryMetrics:
    z_average: float | None = None
    pdi: float | None = None
    peak_sizes: list[float] = field(default_factory=list)
    peak_areas: list[float] = field(default_factory=list)
    count_rate: float | None = None
    measurement_count: int | None = None
    max_z_average: float | None = None
    max_pdi: float | None = None


@dataclass
class DistributionData:
    diameter_nm: list[float] = field(default_factory=list)
    intensity: list[float] = field(default_factory=list)
    volume: list[float] = field(default_factory=list)
    number: list[float] = field(default_factory=list)
    source_columns: dict[str, str] = field(default_factory=dict)

    def has_any_signal(self) -> bool:
        return bool(self.intensity or self.volume or self.number)


@dataclass
class DerivedMetrics:
    primary_peak_nm: float | None = None
    secondary_peak_nm: float | None = None
    peak_count: int | None = None
    peak_width_ratio: float | None = None
    peak_symmetry: float | None = None
    d10_nm: float | None = None
    d50_nm: float | None = None
    d90_nm: float | None = None
    tail_index_percent: float | None = None
    width_ratio: float | None = None
    skewness: float | None = None
    aggregation_risk: str | None = None
    aggregation_index: float | None = None
    quality_score: float | None = None
    correlogram_noise_score: float | None = None


@dataclass
class AngleSummary:
    """Per-scattering-angle view of a measurement.

    Dual-angle DLS runs (e.g. forward 12.78° + back 174.7°) report different
    apparent sizes at each angle, so blending them hides real structure. Each
    ``AngleSummary`` keeps one angle's aggregated numbers alongside the
    lot-level combined metrics.
    """

    label: str
    angle_degrees: float | None = None
    position: str | None = None  # "forward" or "back"
    count: int | None = None
    z_average: float | None = None
    pdi: float | None = None
    max_z_average: float | None = None
    primary_peak_nm: float | None = None
    d50_nm: float | None = None
    replicate_count: int | None = None


@dataclass
class MeasurementFlag:
    label: str
    severity: str = "watch"
    evidence: str | None = None


@dataclass
class Observation:
    """Normalized scientific finding derived from measurements or analysis."""

    label: str
    category: str
    evidence: str
    sample_name: str | None = None
    severity: str = "info"
    confidence: str = "medium"
    source_type: str = "measurement"
    source_id: str | None = None
    recommendation: str | None = None


@dataclass
class ChromatographyPeak:
    """One chromatographic peak after parsing or manual entry."""

    peak_id: str
    name: str | None = None
    role: str = "unknown"  # parent, known_impurity, unknown, standard, recovery_control
    retention_time_min: float | None = None
    area: float | None = None
    area_percent: float | None = None
    height: float | None = None
    width_seconds: float | None = None
    tailing_factor: float | None = None
    resolution: float | None = None
    signal_to_noise: float | None = None
    integration_start_min: float | None = None
    integration_end_min: float | None = None
    coelution_suspected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChromatogramTrace:
    """Decoded raw chromatogram time/intensity evidence for one detector signal."""

    source_file: str
    time_min: list[float] = field(default_factory=list)
    intensity: list[float] = field(default_factory=list)
    detector: str | None = None
    signal_name: str | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChromatographyMeasurement:
    """Raw chromatographic evidence from one analytical run.

    This is a future-facing model only. It does not parse HPLC/SEC files yet;
    ingestion adapters should populate it once chromatography support is added.
    """

    sample_name: str
    technique: str = "HPLC"
    method_name: str | None = None
    injection_id: str | None = None
    timepoint: str | None = None
    replicate_id: str | None = None
    source_files: list[str] = field(default_factory=list)
    peaks: list[ChromatographyPeak] = field(default_factory=list)
    chromatogram_traces: list[ChromatogramTrace] = field(default_factory=list)
    total_area: float | None = None
    parent_peak_id: str | None = None
    recovery_percent: float | None = None
    replicate_rsd_percent: float | None = None
    baseline_status: str | None = None
    integration_method: str | None = None
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FiltrationTrace:
    """Generic filtration-device trace without device-specific assumptions."""

    time_values: list[float] = field(default_factory=list)
    time_unit: str | None = None
    time_minutes: list[float] = field(default_factory=list)
    pressure_values: list[float] = field(default_factory=list)
    pressure_unit: str | None = None
    pressure_kpa: list[float] = field(default_factory=list)
    flow_rate_values: list[float] = field(default_factory=list)
    flow_rate_unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FiltrationMeasurement:
    """Orthogonal filtration evidence for one sample.

    This is intentionally small: it lets LabAssistant relate DLS forward-scatter
    attributes to a separate filtration behavior measurement without treating
    filtration as another DLS-derived metric.
    """

    sample_name: str
    technique: str = "Filtration"
    difficulty_score: float | None = None
    filtration_time_minutes: float | None = None
    pressure: float | None = None
    pressure_unit: str | None = None
    pressure_kpa: float | None = None
    filter_type: str | None = None
    clogging_observed: bool | None = None
    notes: str | None = None
    source: str = "manual_entry"
    source_file: str | None = None
    warnings: list[str] = field(default_factory=list)
    trace: FiltrationTrace | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MassBalanceAssessment:
    """Mass-balance interpretation over chromatographic evidence."""

    sample_name: str
    parent_change_percent: float | None = None
    parent_area_percent: float | None = None
    total_area_change_percent: float | None = None
    known_impurity_change_percent: float | None = None
    known_impurity_area_percent: float | None = None
    unknown_area_percent: float | None = None
    missing_area_change_percent: float | None = None
    retention_time_shift_min: float | None = None
    recovery_percent: float | None = None
    replicate_rsd_percent: float | None = None
    total_area_conserved: bool | None = None
    observations: list[Observation] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Experiment:
    """Instrument-agnostic container for one analytical experiment.

    An ``Experiment`` is the top-level unit LabAssistant reasons about. It holds
    whatever raw evidence an importer produced (DLS ``Measurement`` objects, HPLC
    ``ChromatographyMeasurement`` objects, future SEC/UV/ELISA records) alongside
    the normalized ``Observation`` stream. The intelligence layer (Investigator,
    mass-balance reasoning) consumes ``observations`` and never touches raw files,
    so a new instrument only needs an importer that fills this object.

    ``measurements`` is deliberately untyped (``Any``) so the same container works
    for every technique. ``instrument`` and ``technique`` describe provenance;
    ``metadata`` carries importer-specific context (sequence name, operator,
    archive entry counts, unsupported sections, etc.).
    """

    experiment_id: str
    label: str
    instrument: str | None = None
    technique: str | None = None
    source_path: str | None = None
    created_at: str | None = None
    measurements: list[Any] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    unsupported_sections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)

    def observations_by_category(self) -> dict[str, list[Observation]]:
        grouped: dict[str, list[Observation]] = {}
        for observation in self.observations:
            grouped.setdefault(observation.category, []).append(observation)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "label": self.label,
            "instrument": self.instrument,
            "technique": self.technique,
            "source_path": self.source_path,
            "created_at": self.created_at,
            "measurements": [
                measurement.to_dict() if hasattr(measurement, "to_dict") else measurement
                for measurement in self.measurements
            ],
            "observations": [asdict(observation) for observation in self.observations],
            "unsupported_sections": list(self.unsupported_sections),
            "metadata": self.metadata,
        }


@dataclass
class InvestigatorFinding:
    """One question/answer pair produced by the Scientific Investigator."""

    question: str
    answer: str
    details: list[str] = field(default_factory=list)


@dataclass
class InvestigatorReport:
    """Deterministic reasoning output over an Experiment's Observations.

    The Investigator consumes Observations only. It never reads raw files or
    Measurements, which keeps the reasoning layer instrument-agnostic: any
    importer that emits Observations can be interpreted by the same engine.
    """

    experiment_id: str
    what_happened: str
    is_complete: bool
    is_interpretable: bool
    completeness_gaps: list[str] = field(default_factory=list)
    interpretation_blockers: list[str] = field(default_factory=list)
    confidence_improvers: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    findings: list[InvestigatorFinding] = field(default_factory=list)
    observation_counts: dict[str, int] = field(default_factory=dict)

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
            "findings": [asdict(finding) for finding in self.findings],
            "observation_counts": dict(self.observation_counts),
        }


@dataclass
class Measurement:
    metadata: MeasurementMetadata
    summary_metrics: SummaryMetrics = field(default_factory=SummaryMetrics)
    distributions: dict[str, DistributionData] = field(default_factory=dict)
    correlogram: list[dict[str, float]] = field(default_factory=list)
    derived_metrics: DerivedMetrics = field(default_factory=DerivedMetrics)
    angle_summaries: list[AngleSummary] = field(default_factory=list)
    flags: list[MeasurementFlag] = field(default_factory=list)
    interpretation: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def sample_name(self) -> str:
        return self.metadata.sample_name

    def add_flag(self, label: str, severity: str = "watch", evidence: str | None = None) -> None:
        self.flags.append(MeasurementFlag(label=label, severity=severity, evidence=evidence))

    def merge(self, other: Measurement) -> Measurement:
        """Merge another partial measurement into this object.

        Existing scalar values are kept unless they are missing. Collection
        fields are combined, allowing multiple importer outputs to become one
        experiment-level measurement.
        """
        self.metadata.source_files = list(dict.fromkeys(self.metadata.source_files + other.metadata.source_files))
        self.metadata.raw_fields.update(other.metadata.raw_fields)

        for field_name in ("measurement_datetime", "instrument", "operator", "temperature", "scattering_angle", "method"):
            current_value = getattr(self.metadata, field_name)
            other_value = getattr(other.metadata, field_name)
            if _is_missing(current_value) and not _is_missing(other_value):
                setattr(self.metadata, field_name, other_value)

        for field_name, value in vars(other.summary_metrics).items():
            current_value = getattr(self.summary_metrics, field_name)
            if _is_missing(current_value) and not _is_missing(value):
                setattr(self.summary_metrics, field_name, value)
            elif isinstance(current_value, list) and isinstance(value, list):
                current_value.extend(value)

        for mode, distribution in other.distributions.items():
            if mode not in self.distributions or not self.distributions[mode].has_any_signal():
                self.distributions[mode] = distribution

        for field_name, value in vars(other.derived_metrics).items():
            if _is_missing(getattr(self.derived_metrics, field_name)) and not _is_missing(value):
                setattr(self.derived_metrics, field_name, value)

        self._merge_angle_summaries(other.angle_summaries)

        self.correlogram.extend(other.correlogram)
        self.flags.extend(other.flags)
        self.interpretation.update(other.interpretation)
        self.provenance.update(other.provenance)
        return self

    def _merge_angle_summaries(self, others: list[AngleSummary]) -> None:
        existing = {summary.angle_degrees: summary for summary in self.angle_summaries}
        for other_summary in others:
            current = existing.get(other_summary.angle_degrees)
            if current is None:
                self.angle_summaries.append(other_summary)
                existing[other_summary.angle_degrees] = other_summary
                continue
            for field_name, value in vars(other_summary).items():
                if _is_missing(getattr(current, field_name)) and not _is_missing(value):
                    setattr(current, field_name, value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_missing(value: Any) -> bool:
    return value is None or value == [] or value == {}
