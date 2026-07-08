"""Core LabAssistant analysis package."""

from labassistant.models import (
    AngleSummary,
    ChromatographyMeasurement,
    ChromatographyPeak,
    DerivedMetrics,
    DistributionData,
    Experiment,
    InvestigatorFinding,
    InvestigatorReport,
    MassBalanceAssessment,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    Observation,
    SummaryMetrics,
)
from labassistant.investigator import investigate, investigate_observations
from labassistant.context_engine import (
    ContextPacket,
    ContextRetriever,
    KnowledgeItem,
    KnowledgeStore,
    ResearchJournal,
    ResearchJournalEntry,
)
from labassistant.measurements import measurement_from_dls_result
from labassistant.aggregation import (
    DualAngleAggregation,
    assess_dual_angle_aggregation,
    calculate_aggregation_index,
)

__all__ = [
    "AngleSummary",
    "ChromatographyMeasurement",
    "ChromatographyPeak",
    "ContextPacket",
    "ContextRetriever",
    "DerivedMetrics",
    "DistributionData",
    "DualAngleAggregation",
    "Experiment",
    "InvestigatorFinding",
    "InvestigatorReport",
    "KnowledgeItem",
    "KnowledgeStore",
    "ResearchJournal",
    "ResearchJournalEntry",
    "MassBalanceAssessment",
    "Measurement",
    "MeasurementFlag",
    "MeasurementMetadata",
    "Observation",
    "SummaryMetrics",
    "assess_dual_angle_aggregation",
    "calculate_aggregation_index",
    "investigate",
    "investigate_observations",
    "measurement_from_dls_result",
]
