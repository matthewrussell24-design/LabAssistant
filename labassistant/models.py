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
