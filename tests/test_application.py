import json
from dataclasses import FrozenInstanceError
from io import BytesIO
from pathlib import Path

import pandas as pd
from pytest import approx, raises

from labassistant.application import (
    AGENT_API_VERSION,
    APP_DIRECTION,
    HUMAN_APP_SURFACE,
    ExperimentListing,
    ExperimentComparison,
    ExperimentInvestigation,
    ExperimentBriefPreview,
    ExperimentSaveReceipt,
    ObservationGenerationResult,
    DLSUploadImportResult,
    DLSUploadFileRead,
    DLSUploadGroupRead,
    DLSDecisionRanking,
    DLSNarrative,
    DLSHealthOverview,
    DLSTrendDiagnostics,
    DLSForwardScatterTrendRead,
    FiltrationTrendRead,
    DLSAggregationRead,
    DLSSampleSummaries,
    DLSAngleDetails,
    DLSMetricsProjection,
    DLSDistributionProjection,
    DLSRawEvidence,
    DLSCorrelograms,
    FiltrationImportRead,
    ChromatographyRestoreResult,
    ChromatographyAnalysisResult,
    HistoryOverview,
    RelatedExperiments,
    RelatedScientificContext,
    ResearchJournalRead,
    ScientificNoteReceipt,
    add_scientific_note,
    analyze_dls_dataset,
    analyze_dls_trend_diagnostics,
    analyze_dls_forward_scatter_trends,
    analyze_filtration_follow_up_trends,
    assess_dls_aggregation,
    summarize_dls_samples,
    retrieve_dls_angle_details,
    retrieve_dls_metrics,
    retrieve_dls_distributions,
    retrieve_dls_raw_evidence,
    retrieve_dls_correlograms,
    analyze_dls_uploads,
    analyze_chromatography_source,
    analyze_filtration_csv,
    compare_experiments,
    compose_dls_narrative,
    agent_access_policy,
    app_manifest,
    build_experiment_snapshot,
    dls_experiment_from_samples,
    find_related_experiments,
    generate_observations,
    investigate_experiment,
    produce_experiment_brief,
    rank_dls_decisions,
    get_capability,
    list_capabilities,
    list_experiments,
    retrieve_history_overview,
    retrieve_related_context,
    retrieve_research_journal,
    restore_chromatography_experiment,
    restore_dls_experiment,
    retrieve_experiment,
    save_experiment_history,
    save_experiment_to_memory,
    summarize_dls_health,
)
from labassistant.models import (
    ChromatogramTrace,
    ChromatographyMeasurement,
    ChromatographyPeak,
    Experiment,
    FiltrationMeasurement,
    MassBalanceAssessment,
    Measurement,
    MeasurementMetadata,
    AngleSummary,
    Observation,
)
from labassistant.history import (
    ExperimentRecordNotFoundError,
    MalformedExperimentRecordError,
    save_experiment,
)
from labassistant.context_engine import KnowledgeStore
from labassistant.aggregation import assess_dual_angle_aggregation
from labassistant.interpretation import build_ai_summary, build_data_analysis
from labassistant.trend_analysis import (
    apply_circulation_time,
    apply_filtration_measurement,
    build_filtration_trend_analysis,
    build_forward_scatter_trend_analysis_from_measurements,
    build_data_story,
    control_chart_table,
    replicate_statistics_table,
)
from labassistant.view_models import ParsedSample, build_angle_table, build_metrics_table
from app import (
    distribution_difference_dataframe,
    distribution_series_dataframe,
    dls_metrics_dataframe,
    raw_point_table_dataframe,
)


class RecordingStore:
    def __init__(self):
        self.experiments = []
        self.hypotheses = []
        self.recommendations = []
        self.notes = []

    def add_experiment(self, experiment, *, project_id=None, tags=()):
        self.experiments.append((experiment, project_id, list(tags)))

    def add_hypothesis(self, text, **kwargs):
        self.hypotheses.append((text, kwargs))

    def add_recommendation(self, text, **kwargs):
        self.recommendations.append((text, kwargs))

    def add_note(self, text, **kwargs):
        self.notes.append((text, kwargs))


class NamedUpload(BytesIO):
    def __init__(self, name: str, content: str):
        super().__init__(content.encode("utf-8"))
        self.name = name


def test_app_manifest_declares_standalone_human_first_direction():
    manifest = app_manifest()

    assert manifest["direction"] == APP_DIRECTION
    assert manifest["primary_surface"] == HUMAN_APP_SURFACE
    assert manifest["agent_access"]["api_version"] == AGENT_API_VERSION
    assert "future local agents" in manifest["agent_access"]["intended_clients"]
    assert [capability["name"] for capability in manifest["capabilities"]] == [
        capability.name for capability in list_capabilities()
    ]
    assert "handler" not in manifest["capabilities"][0]


def test_agent_access_policy_is_foundational_not_runtime():
    policy = agent_access_policy()

    assert policy.status == "planned_foundation"
    assert "Experiment" in policy.stable_inputs
    assert "Observation" in policy.stable_inputs
    assert "autonomous lab operation" in policy.current_non_goals
    assert "network service or external API server" in policy.current_non_goals


def test_experiment_snapshot_exposes_stable_summary_not_raw_payload():
    experiment = Experiment(
        experiment_id="exp-1",
        label="Stress study",
        technique="DLS",
        instrument="Zetasizer",
        measurements=[Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        observations=[
            Observation(label="High PDI", category="quality", evidence="PDI 0.41"),
            Observation(label="Forward scatter increased", category="particle_size", evidence="Forward > back"),
            Observation(label="Repeat recommended", category="quality", evidence="Replicate variance"),
        ],
    )

    snapshot = build_experiment_snapshot(experiment)
    payload = snapshot.to_dict()

    assert payload["experiment_id"] == "exp-1"
    assert payload["measurement_count"] == 1
    assert payload["observation_count"] == 3
    assert payload["observation_categories"] == {"quality": 2, "particle_size": 1}
    assert "measurements" not in payload
    assert "observations" not in payload


def test_investigate_experiment_returns_versioned_immutable_evidence():
    experiment = Experiment(
        experiment_id="exp-investigate",
        label="Stress study",
        technique="HPLC",
        observations=[
            Observation(
                label="Total area decreased",
                category="mass_balance",
                evidence="Total area changed by -12%.",
                sample_name="Stress T2",
                severity="review",
                source_type="mass_balance_assessment",
                source_id="assessment-1",
                recommendation="Check recovery.",
            )
        ],
    )

    result = investigate_experiment(experiment)
    experiment.observations[0].label = "Mutated after query"

    assert isinstance(result, ExperimentInvestigation)
    assert result.experiment_id == "exp-investigate"
    assert result.is_complete is True
    assert result.is_interpretable is True
    assert len(result.findings) == 5
    assert result.findings[0].question == "What happened?"
    assert result.observations[0].label == "Total area decreased"
    assert result.observations[0].source_id == "assessment-1"
    assert result.observation_counts == (("review", 1),)
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_investigate_experiment_preserves_empty_evidence_behavior():
    result = investigate_experiment(Experiment(experiment_id="empty", label="Empty"))

    assert result.is_complete is True
    assert result.is_interpretable is False
    assert result.observations == ()
    assert "No substantive observations" in result.interpretation_blockers[0]


def test_produce_experiment_brief_composes_immutable_investigator_preview():
    experiment = Experiment(
        experiment_id="exp-brief",
        label="Stress study",
        technique="HPLC",
        instrument="Chromatography",
        measurements=[ChromatographyMeasurement(sample_name="Stress T2")],
        observations=[
            Observation(
                label="Total area decreased",
                category="mass_balance",
                evidence="Total area changed by -12%.",
                severity="review",
                recommendation="Check recovery.",
            )
        ],
    )

    result = produce_experiment_brief(experiment)
    experiment.label = "Changed"
    experiment.observations[0].label = "Changed"

    assert isinstance(result, ExperimentBriefPreview)
    assert result.experiment.label == "Stress study"
    assert result.experiment.observation_categories == (("mass_balance", 1),)
    assert len(result.sections) == 5
    assert result.sections[0].heading == "What happened?"
    assert result.observations[0].label == "Total area decreased"
    assert result.is_interpretable is True
    payload = result.to_dict()
    assert payload["experiment"]["observation_categories"] == {"mass_balance": 1}
    assert payload["api_version"] == AGENT_API_VERSION


def test_produce_experiment_brief_rejects_non_experiment_input():
    with raises(TypeError, match="must be an Experiment"):
        produce_experiment_brief(object())


def test_retrieve_related_context_returns_immutable_ranked_provenance(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    experiment = Experiment(
        experiment_id="exp-context",
        label="OpenLab stability run",
        technique="HPLC",
        instrument="Agilent 1290",
        source_path="/data/run.olax",
        observations=[
            Observation(
                label="Missing peak table",
                category="data_completeness",
                evidence="No peak table was exported.",
                severity="watch",
                source_type="openlab_olax",
                source_id="run.olax",
                recommendation="Export a peak table.",
            )
        ],
    )
    store.add_experiment(experiment, project_id="stability", tags=["openlab", "special"])
    store.add_note(
        "Review OpenLab integration export.",
        title="Operator note",
        experiment_id=experiment.experiment_id,
        tags=["openlab", "special"],
    )

    result = retrieve_related_context(
        "Can the OpenLab run support integration?",
        tags=("special",),
        store=store,
    )

    assert isinstance(result, RelatedScientificContext)
    assert result.relevant_experiments[0].title == "OpenLab stability run"
    assert result.relevant_experiments[0].project_id == "stability"
    assert {"openlab", "special"}.issubset(result.relevant_experiments[0].tags)
    assert result.relevant_observations[0].source_id == "run.olax"
    assert result.related_notes[0].title == "Operator note"
    assert result.confidence == "medium"
    payload = result.to_dict()
    assert payload["api_version"] == AGENT_API_VERSION
    assert "payload" not in payload["relevant_experiments"][0]


def test_retrieve_related_context_preserves_empty_memory_behavior(tmp_path):
    result = retrieve_related_context(
        "What happened in the DLS run?",
        knowledge_path=tmp_path / "knowledge.sqlite",
    )

    assert result.relevant_experiments == ()
    assert result.confidence == "low"
    assert "No matching local memory" in result.caveats[0]


def test_retrieve_related_context_validates_question_and_limit(tmp_path):
    with raises(ValueError, match="question"):
        retrieve_related_context(" ", knowledge_path=tmp_path / "knowledge.sqlite")
    with raises(ValueError, match="limit"):
        retrieve_related_context("DLS", limit=0, knowledge_path=tmp_path / "knowledge.sqlite")


def test_retrieve_research_journal_preserves_grouping_filters_and_export(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    experiment = Experiment(
        experiment_id="exp-journal",
        label="HPLC stability run",
        technique="HPLC",
        instrument="Agilent 1290",
        source_path="/data/run.olax",
        measurements=[ChromatographyMeasurement(sample_name="Sample A")],
        observations=[
            Observation(
                label="Missing peak table",
                category="data_completeness",
                evidence="No peak table was exported.",
                recommendation="Export a peak table.",
            )
        ],
    )
    store.add_experiment(experiment, tags=["openlab", "stability"])
    store.add_hypothesis(
        "Quantitative mass balance needs peak areas.",
        experiment_id=experiment.experiment_id,
        tags=["openlab"],
    )
    store.add_note(
        "Review integration settings.",
        experiment_id=experiment.experiment_id,
        tags=["openlab"],
    )

    result = retrieve_research_journal(
        keyword="mass balance",
        tag="openlab",
        instrument="Agilent",
        sample="Sample A",
        store=store,
    )

    assert isinstance(result, ResearchJournalRead)
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.entry_id == experiment.experiment_id
    assert entry.samples == ("Sample A",)
    assert entry.hypotheses == ("Quantitative mass balance needs peak areas.",)
    assert entry.notes == ("Review integration settings.",)
    assert "_Filters: keyword: mass balance, tag: openlab, instrument: Agilent, sample: Sample A_" in result.markdown
    assert "## HPLC stability run" in result.markdown
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_retrieve_research_journal_handles_empty_and_standalone_notes(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    empty = retrieve_research_journal(keyword="missing", store=store)
    assert empty.entries == ()
    assert "No journal entries matched" in empty.markdown

    store.add_note("Compare DLS and HPLC.", title="Synthesis", tags=["cross-technique"])
    result = retrieve_research_journal(tag="cross-technique", store=store)

    assert len(result.entries) == 1
    assert result.entries[0].experiment_id is None
    assert result.entries[0].notes == ("Compare DLS and HPLC.",)


def test_add_scientific_note_validates_normalizes_and_returns_receipt(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")

    receipt = add_scientific_note(
        "  Compare DLS aggregation with HPLC recovery.  ",
        title="  Cross-technique review  ",
        instrument_id="  Agilent 1290  ",
        tags=(" Weekend ", "dls", "Weekend", ""),
        store=store,
    )

    assert isinstance(receipt, ScientificNoteReceipt)
    assert receipt.title == "Cross-technique review"
    assert receipt.instrument_id == "Agilent 1290"
    assert receipt.tags == ("dls", "weekend")
    assert receipt.confidence == "human"
    assert receipt.created_at
    assert receipt.to_dict()["api_version"] == AGENT_API_VERSION
    notes = store.list_items(entity_type="note")
    assert len(notes) == 1
    assert notes[0].item_id == receipt.item_id
    assert notes[0].text == "Compare DLS aggregation with HPLC recovery."


def test_add_scientific_note_defaults_title_and_rejects_empty_text(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    receipt = add_scientific_note("Useful context", store=store)
    assert receipt.title == "Research note"

    with raises(ValueError, match="text"):
        add_scientific_note("  ", store=store)
    assert len(store.list_items(entity_type="note")) == 1


def test_save_experiment_history_validates_copies_lineage_and_returns_receipt(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    measurement = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))

    receipt = save_experiment_history(
        [measurement],
        "  Follow-up run  ",
        loaded_from_record_id="  prior-id  ",
        loaded_from_label="  Baseline  ",
        history_path=history_path,
    )

    assert isinstance(receipt, ExperimentSaveReceipt)
    assert receipt.label == "Follow-up run"
    assert receipt.measurement_count == 1
    assert receipt.loaded_from_record_id == "prior-id"
    assert receipt.saved_at
    assert receipt.to_dict()["api_version"] == AGENT_API_VERSION
    assert "history_lineage" not in measurement.provenance
    saved = json.loads(history_path.read_text(encoding="utf-8"))
    assert saved["id"] == receipt.record_id
    assert saved["measurements"][0]["provenance"]["history_lineage"] == {
        "loaded_from_label": "Baseline",
        "loaded_from_record_id": "prior-id",
        "save_semantics": "append_new_version",
    }


def test_save_experiment_history_rejects_missing_or_unserializable_evidence(tmp_path):
    history_path = tmp_path / "experiments.jsonl"

    with raises(ValueError, match="At least one measurement"):
        save_experiment_history([], history_path=history_path)
    with raises(TypeError, match="to_dict"):
        save_experiment_history([object()], history_path=history_path)
    assert not history_path.exists()


def test_retrieve_experiment_returns_read_only_metadata_and_fresh_measurements(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    saved = save_experiment(
        [Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        label="Run A",
        history_path=history_path,
    )

    retrieved = retrieve_experiment(saved.id, history_path=history_path)
    first = retrieved.restore_measurements()
    first[0].metadata.sample_name = "Changed by caller"
    second = retrieved.restore_measurements()

    assert retrieved.to_dict() == {
        "record_id": saved.id,
        "saved_at": saved.saved_at,
        "label": "Run A",
        "measurement_count": 1,
        "api_version": AGENT_API_VERSION,
    }
    assert second[0].sample_name == "Lot 1"
    assert second[0].provenance["loaded_from_history"] == {
        "record_id": saved.id,
        "label": "Run A",
        "saved_at": saved.saved_at,
    }


def test_list_experiments_returns_empty_tuple_when_no_history(tmp_path):
    assert list_experiments(history_path=tmp_path / "experiments.jsonl") == ()


def test_list_experiments_orders_newest_first_with_metadata_only(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    older = save_experiment(
        [Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        label="Run A",
        history_path=history_path,
    )
    newer = save_experiment(
        [
            Measurement(metadata=MeasurementMetadata(sample_name="Lot 1")),
            Measurement(metadata=MeasurementMetadata(sample_name="Lot 2")),
        ],
        label="Run B",
        history_path=history_path,
    )

    listings = list_experiments(history_path=history_path)

    assert isinstance(listings, tuple)
    assert all(isinstance(listing, ExperimentListing) for listing in listings)
    # Same-second saves are ordered by append position: the last saved wins.
    assert [listing.record_id for listing in listings] == [newer.id, older.id]
    assert listings[0].measurement_count == 2
    assert listings[0].label == "Run B"
    # Metadata only: no measurement payload is exposed through a listing.
    assert not hasattr(listings[0], "measurements")
    assert listings[0].to_dict() == {
        "record_id": newer.id,
        "saved_at": newer.saved_at,
        "label": "Run B",
        "measurement_count": 2,
        "api_version": AGENT_API_VERSION,
    }


def test_list_experiments_skips_malformed_lines(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    saved = save_experiment(
        [Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        label="Run A",
        history_path=history_path,
    )
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write("{not valid json}\n")

    listings = list_experiments(history_path=history_path)

    assert [listing.record_id for listing in listings] == [saved.id]


def test_compare_experiments_returns_versioned_immutable_drift_result(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    baseline = save_experiment(
        [Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        label="Baseline",
        history_path=history_path,
    )
    baseline.measurements[0]["summary_metrics"] = {"z_average": 100.0, "pdi": 0.2}
    history_path.write_text(json.dumps(baseline.to_dict()) + "\n", encoding="utf-8")
    current = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))
    current.summary_metrics.z_average = 130.0
    current.summary_metrics.pdi = 0.21

    result = compare_experiments(
        [current], baseline_record_id=baseline.id, history_path=history_path
    )

    assert isinstance(result, ExperimentComparison)
    assert result.baseline_record_id == baseline.id
    assert result.baseline_label == "Baseline"
    assert result.rows[0].drift == "Z-average drift"
    assert result.rows[0].z_change_percent == approx(30.0)
    assert result.drifted_sample_count == 1
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_compare_experiments_handles_absent_history_and_new_samples(tmp_path):
    current = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))

    result = compare_experiments([current], history_path=tmp_path / "missing.jsonl")

    assert result.baseline_record_id is None
    assert result.rows[0].drift == "New sample"
    assert result.drifted_sample_count == 0


def test_find_related_experiments_returns_ranked_versioned_matches(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    near = Measurement(metadata=MeasurementMetadata(sample_name="Near"))
    near.summary_metrics.z_average = 100.0
    near.summary_metrics.pdi = 0.20
    far = Measurement(metadata=MeasurementMetadata(sample_name="Far"))
    far.summary_metrics.z_average = 400.0
    far.summary_metrics.pdi = 0.40
    save_experiment([far, near], label="Baseline", history_path=history_path)
    query = Measurement(metadata=MeasurementMetadata(sample_name="Query"))
    query.summary_metrics.z_average = 105.0
    query.summary_metrics.pdi = 0.21

    result = find_related_experiments(query, top_n=2, history_path=history_path)

    assert isinstance(result, RelatedExperiments)
    assert result.query_sample_name == "Query"
    assert [match.sample_name for match in result.matches] == ["Near", "Far"]
    assert result.matches[0].distance <= result.matches[1].distance
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_find_related_experiments_handles_empty_history_exclusion_and_limit(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    query = Measurement(metadata=MeasurementMetadata(sample_name="Query"))
    assert find_related_experiments(query, history_path=history_path).matches == ()

    saved = save_experiment([query], label="Only", history_path=history_path)
    excluded = find_related_experiments(
        query, exclude_record_id=saved.id, history_path=history_path
    )
    assert excluded.matches == ()
    with raises(ValueError, match="top_n"):
        find_related_experiments(query, top_n=0, history_path=history_path)


def test_retrieve_history_overview_returns_immutable_summary_and_trends(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    measurement = Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))
    measurement.summary_metrics.z_average = 125.0
    measurement.summary_metrics.pdi = 0.23
    saved = save_experiment([measurement], label="Run A", history_path=history_path)

    result = retrieve_history_overview(history_path=history_path)

    assert isinstance(result, HistoryOverview)
    assert result.summaries[0].record_id == saved.id
    assert result.summaries[0].median_z_average_nm == 125.0
    assert result.trend_points[0].sample_name == "Lot 1"
    assert result.trend_points[0].pdi == 0.23
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_retrieve_history_overview_handles_missing_and_empty_measurements(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    assert retrieve_history_overview(history_path=history_path) == HistoryOverview((), ())
    save_experiment([], label="Empty", history_path=history_path)

    result = retrieve_history_overview(history_path=history_path)

    assert len(result.summaries) == 1
    assert result.summaries[0].measurement_count == 0
    assert result.trend_points == ()


def test_restore_dls_experiment_rehydrates_a_saved_record(tmp_path):
    fixture_dir = Path(__file__).parent / "fixtures"
    history_path = tmp_path / "experiments.jsonl"
    measurements = _import_fixture_measurements(fixture_dir)
    record = save_experiment(measurements, label="Saved run", history_path=history_path)

    result = restore_dls_experiment(record.id, history_path=history_path)

    assert result.experiment.label == "Saved run"
    assert result.experiment.technique == "DLS"
    assert result.measurements[0].sample_name == "Lot 1"
    assert result.measurements[0].primary_peak_nm is not None
    assert "measurements" in result.to_dict()


def test_restore_dls_experiment_reports_missing_record(tmp_path):
    with raises(ExperimentRecordNotFoundError):
        restore_dls_experiment("does-not-exist", history_path=tmp_path / "experiments.jsonl")


def test_restore_chromatography_experiment_rebuilds_nested_evidence(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    measurement = ChromatographyMeasurement(
        sample_name="Formulation A",
        timepoint="T0",
        injection_id="inj-1",
        source_files=["run.olax"],
        peaks=[
            ChromatographyPeak(
                peak_id="parent", role="parent", retention_time_min=5.2, area=900.0
            ),
            ChromatographyPeak(peak_id="unknown", role="unknown", area=100.0),
        ],
        chromatogram_traces=[
            ChromatogramTrace(
                source_file="run.olax", time_min=[0.0, 1.0], intensity=[1.0, 2.0]
            )
        ],
        total_area=1000.0,
        parent_peak_id="parent",
    )
    saved = save_experiment([measurement], label="HPLC Run", history_path=history_path)

    result = restore_chromatography_experiment(saved.id, history_path=history_path)

    assert isinstance(result, ChromatographyRestoreResult)
    assert result.record_id == saved.id
    assert result.experiment.label == "HPLC Run"
    assert result.experiment.technique == "HPLC"
    assert result.experiment.observation_count > 0
    assert result.measurements[0].peak_count == 2
    assert result.measurements[0].chromatogram_trace_count == 1
    assert result.source_files == ("run.olax",)
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_restore_chromatography_experiment_rejects_non_chromatography_records(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    dls = save_experiment(
        [Measurement(metadata=MeasurementMetadata(sample_name="Lot 1"))],
        history_path=history_path,
    )
    empty = save_experiment([], history_path=history_path)

    with raises(MalformedExperimentRecordError, match="not a chromatography"):
        restore_chromatography_experiment(dls.id, history_path=history_path)
    with raises(MalformedExperimentRecordError, match="no chromatography"):
        restore_chromatography_experiment(empty.id, history_path=history_path)


def test_restore_chromatography_experiment_rejects_malformed_nested_evidence(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    saved = save_experiment(
        [ChromatographyMeasurement(sample_name="Sample A")],
        history_path=history_path,
    )
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    payload["measurements"][0]["peaks"] = "not-a-list"
    history_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with raises(MalformedExperimentRecordError, match="invalid measurement payload"):
        restore_chromatography_experiment(saved.id, history_path=history_path)


def _import_fixture_measurements(fixture_dir):
    from labassistant.importers.measurement_importer import (
        build_import_preview,
        import_measurement_groups,
    )

    paths = [
        fixture_dir / "Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
        fixture_dir / "Size Distribution by Intensity Lot 1.xlsx",
        fixture_dir / "Correlogram lot 1.xlsx",
    ]
    handles = [path.open("rb") for path in paths]
    try:
        preview = build_import_preview(handles)
        groups = [group for group in preview.groups if group.summary_files or group.intensity_files]
        imports = import_measurement_groups(groups)
    finally:
        for handle in handles:
            handle.close()
    return [result.measurement for result in imports if result.measurement is not None]


def test_dls_experiment_creation_is_available_outside_streamlit():
    sample = ParsedSample(
        name="Lot 1",
        file_name="lot1.csv",
        data=None,
        metadata={},
        metrics={
            "PDI": 0.42,
            "Secondary Peak": None,
            "Tail Index": None,
            "Width Ratio": None,
            "Aggregation Index": None,
            "Correlogram Noise": None,
        },
        warnings=["Moderate PDI"],
        source_text="",
        measurement=Measurement(metadata=MeasurementMetadata(sample_name="Lot 1")),
    )

    experiment = dls_experiment_from_samples([sample], label="Run A", source_files=["lot1.csv"])

    assert experiment.label == "Run A"
    assert experiment.technique == "DLS"
    assert experiment.measurements[0].sample_name == "Lot 1"
    assert experiment.metadata["source_files"] == ["lot1.csv"]
    assert [observation.label for observation in experiment.observations] == ["High variability"]


def test_generate_observations_returns_immutable_dls_findings_and_fresh_domain_copies():
    sample = ParsedSample(
        name="Lot 1",
        file_name="lot1.csv",
        data=None,
        metadata={},
        metrics={"PDI": 0.42, "Correlogram Noise": None},
        warnings=["Moderate PDI"],
        source_text="",
        measurement=Measurement(metadata=MeasurementMetadata(sample_name="Lot 1")),
    )

    result = generate_observations([sample], technique=" dls ")

    assert isinstance(result, ObservationGenerationResult)
    assert result.technique == "DLS"
    assert result.observations[0].label == "High variability"
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    first = result.restore_observations()
    first[0].label = "Changed"
    assert result.restore_observations()[0].label == "High variability"


def test_generate_observations_uses_chromatography_and_filtration_domain_rules():
    chromatography = ChromatographyMeasurement(
        sample_name="Stress T2",
        peaks=[ChromatographyPeak(peak_id="unknown", role="unknown", area_percent=1.2)],
    )
    assessment = MassBalanceAssessment(sample_name="Stress T2", total_area_change_percent=-9.0)
    chromatography_result = generate_observations(
        [chromatography], technique="HPLC", assessment=assessment
    )
    filtration_result = generate_observations(
        [FiltrationMeasurement(sample_name="Stress T2", difficulty_score=4)],
        technique="filtration",
    )

    assert chromatography_result.technique == "Chromatography"
    assert {item.label for item in chromatography_result.observations} >= {
        "Unknown peak appeared",
        "Total area decreased",
    }
    assert [item.label for item in filtration_result.observations] == [
        "Filtration difficulty elevated"
    ]


def test_generate_observations_rejects_empty_mismatched_and_unsupported_evidence():
    with raises(ValueError, match="At least one evidence"):
        generate_observations([], technique="DLS")
    with raises(TypeError, match="chromatography measurements"):
        generate_observations(
            [object()],
            technique="HPLC",
            assessment=MassBalanceAssessment(sample_name="Sample"),
        )
    with raises(ValueError, match="Unsupported observation technique"):
        generate_observations([object()], technique="microscopy")


def test_analyze_dls_dataset_runs_file_import_and_summary_outside_ui_code():
    fixture_dir = Path(__file__).parent / "fixtures"
    result = analyze_dls_dataset(
        [
            fixture_dir / "Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
            fixture_dir / "Size Distribution by Intensity Lot 1.xlsx",
            fixture_dir / "Correlogram lot 1.xlsx",
        ],
        label="Desktop proof",
    )

    assert result.experiment.label == "Desktop proof"
    assert result.experiment.technique == "DLS"
    assert result.experiment.measurement_count == 1
    assert result.measurements[0].sample_name == "Lot 1"
    assert result.measurements[0].primary_peak_nm == approx(267.2, abs=0.1)
    assert result.measurements[0].aggregation_risk == "High"
    assert result.import_errors == ()
    assert "measurements" in result.to_dict()


def test_analyze_dls_uploads_preserves_preview_diagnostics_and_restores_fresh_samples():
    result = analyze_dls_uploads(
        [
            NamedUpload(
                "Lot 1 summary.csv",
                "Index,Sample Name,Scattering Collection (°),Z-Average (nm),PDI\n"
                "1,Lot 1,173,125,0.21\n",
            ),
            NamedUpload(
                "Lot 1 intensity distribution.csv",
                "Diameter (nm),Intensity Rep 1 (%)\n50,5\n100,100\n",
            ),
        ]
    )

    assert isinstance(result, DLSUploadImportResult)
    assert result.preview_rows() == [
        {
            "Lot": "Lot 1",
            "Summary file": "Lot 1 summary.csv",
            "Intensity file": "Lot 1 intensity distribution.csv",
            "Correlogram file": "",
            "Status": "Missing correlogram",
        }
    ]
    assert result.groups[0].files[0].source_text.startswith("Index,Sample Name")
    assert result.source_files == (
        "Lot 1 summary.csv",
        "Lot 1 intensity distribution.csv",
    )
    assert result.import_errors == ()
    assert result.measurements[0].sample_name == "Lot 1"
    first = result.restore_samples()
    first[0].name = "Changed"
    assert result.restore_samples()[0].name == "Lot 1"
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_analyze_dls_uploads_validates_generic_seekable_sources():
    with raises(ValueError, match="at least one uploaded"):
        analyze_dls_uploads([])
    with raises(TypeError, match="file name"):
        analyze_dls_uploads([BytesIO(b"data")])
    with raises(TypeError, match="readable"):
        analyze_dls_uploads([type("Named", (), {"name": "sample.csv"})()])


def _decision_sample(name: str, pdi: float, warnings: list[str]) -> ParsedSample:
    return ParsedSample(
        name=name,
        file_name=f"{name}.csv",
        data=None,
        metadata={},
        metrics={
            "Data Type": "Distribution Curve",
            "Z-Average": 100.0,
            "PDI": pdi,
            "Max Z-Average": None,
            "Max PDI": None,
            "Measurement Count": None,
            "Scattering Angles": None,
            "Primary Peak": 100.0,
            "Secondary Peak": None,
            "Count Rate": None,
            "Tail Index": 0.0,
            "Width Ratio": 3.0,
            "D10": 50.0,
            "D50": 100.0,
            "D90": 150.0,
            "Diameter Column": "Diameter",
            "Preferred Distribution": "Intensity",
            "Measurement Date": None,
        },
        warnings=warnings,
        source_text="",
        measurement=Measurement(metadata=MeasurementMetadata(sample_name=name)),
    )


def test_rank_dls_decisions_preserves_screening_order_and_returns_immutable_rows():
    result = rank_dls_decisions(
        [
            _decision_sample("clean", 0.12, []),
            _decision_sample("flagged", 0.35, ["Moderate PDI"]),
        ]
    )

    assert isinstance(result, DLSDecisionRanking)
    assert result.best_candidate == "clean (Normal)"
    assert result.attention_candidate == "flagged (Watch)"
    assert result.flagged_count == 1
    assert result.flagged_label == "1 of 2"
    assert result.attention_rows[0].sample_name == "flagged"
    assert result.attention_rows[0].reason == "PDI 0.35"
    assert result.next_check == "Inspect flagged first: PDI 0.35."
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_rank_dls_decisions_preserves_alphabetical_tie_breaking_and_validation():
    result = rank_dls_decisions(
        [_decision_sample("beta", 0.12, []), _decision_sample("alpha", 0.12, [])]
    )

    assert [row.sample_name for row in result.attention_rows] == ["alpha", "beta"]
    assert result.best_candidate == "alpha (Normal)"
    assert result.attention_candidate == "alpha (Normal)"
    with raises(ValueError, match="At least one parsed DLS sample"):
        rank_dls_decisions([])
    with raises(TypeError, match="requires parsed samples"):
        rank_dls_decisions([object()])


def test_compose_dls_narrative_preserves_findings_and_story_as_immutable_sections():
    samples = [
        _decision_sample("clean", 0.12, []),
        _decision_sample("flagged", 0.35, ["Moderate PDI"]),
    ]
    result = compose_dls_narrative(samples)
    metrics = build_metrics_table(samples)

    assert isinstance(result, DLSNarrative)
    assert [section.heading for section in result.automated_findings] == [
        "Main Finding",
        "Samples Needing Review",
        "Why They Were Flagged",
        "What Looks Normal",
        "Suggested Next Check",
    ]
    assert "flagged: PDI 0.35" in result.automated_findings[1].bullets
    assert [section.heading for section in result.data_story] == [
        "What Changed",
        "What Stayed Stable",
        "Needs Attention",
    ]
    assert {
        section.heading: list(section.bullets)
        for section in result.automated_findings
    } == build_ai_summary(samples, metrics)
    assert {
        section.heading: list(section.bullets) for section in result.data_story
    } == build_data_story(samples, metrics)
    assert [section.heading for section in result.detailed_analysis] == [
        "Main Finding",
        "What Is Driving It",
        "How To Judge It",
    ]
    assert {
        section.heading: list(section.bullets)
        for section in result.detailed_analysis
    } == build_data_analysis(samples, metrics)
    assert result.to_dict()["automated_findings"][0]["heading"] == "Main Finding"
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.data_story[0].heading = "Changed"


def test_compose_dls_narrative_validates_parsed_samples():
    with raises(ValueError, match="At least one parsed DLS sample"):
        compose_dls_narrative([])
    with raises(TypeError, match="requires parsed samples"):
        compose_dls_narrative([object()])


def test_summarize_dls_health_preserves_screening_weights_counts_and_medians():
    result = summarize_dls_health(
        [
            _decision_sample("clean", 0.12, []),
            _decision_sample("watch", 0.35, ["Moderate PDI"]),
            _decision_sample("review", 0.50, ["High PDI"]),
        ]
    )

    assert isinstance(result, DLSHealthOverview)
    assert result.screening_score == 63
    assert result.sample_count == 3
    assert result.flagged_count == 2
    assert result.review_count == 1
    assert result.median_z_average_nm == 100.0
    assert result.median_tail_percent == 0.0
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.screening_score = 100


def test_summarize_dls_health_validates_parsed_samples():
    with raises(ValueError, match="At least one parsed DLS sample"):
        summarize_dls_health([])
    with raises(TypeError, match="requires parsed samples"):
        summarize_dls_health([object()])

    missing = _decision_sample("missing", 0.12, [])
    missing.metrics["Z-Average"] = None
    missing.metrics["Tail Index"] = None
    result = summarize_dls_health([missing])
    assert result.median_z_average_nm is None
    assert result.median_tail_percent is None


def test_analyze_dls_trend_diagnostics_preserves_rows_and_order_without_pandas():
    samples = [
        _decision_sample("A", 0.20, []),
        _decision_sample("B", 0.21, []),
        _decision_sample("C", 0.22, []),
    ]
    for sample, z_average, replicates in zip(
        samples,
        (100.0, 110.0, 125.0),
        ([99, 100, 101], [106, 110, 121], [120, 126, 129]),
    ):
        sample.metrics["Z-Average"] = z_average
        sample.measurement.provenance["replicate_metrics"] = {
            "Z-Average": replicates
        }

    result = analyze_dls_trend_diagnostics(samples)
    metrics = build_metrics_table(samples)

    assert isinstance(result, DLSTrendDiagnostics)
    assert [row.sample_name for row in result.control_chart_rows[:3]] == ["A", "B", "C"]
    assert [row.sample_name for row in result.replicate_statistics_rows] == [
        "A",
        "B",
        "C",
    ]
    assert [row.to_dict() for row in result.control_chart_rows] == [
        {
            "sample_name": str(row["Sample"]),
            "metric": str(row["Metric"]),
            "value": float(row["Value"]),
            "mean": float(row["Mean"]),
            "warning_low": float(row["Warning Low"]),
            "warning_high": float(row["Warning High"]),
            "action_low": float(row["Action Low"]),
            "action_high": float(row["Action High"]),
            "zone": str(row["Zone"]),
        }
        for row in control_chart_table(samples, metrics).to_dict(orient="records")
    ]
    expected_replicates = replicate_statistics_table(samples)
    assert [row.to_dict() for row in result.replicate_statistics_rows] == [
        {
            "sample_name": str(row["Sample"]),
            "metric": str(row["Metric"]),
            "count": int(row["N"]),
            "mean": float(row["Mean"]),
            "standard_deviation": float(row["SD"]),
            "relative_standard_deviation_percent": float(row["%RSD"]),
            "drift": str(row["Drift"]),
            "outliers": str(row["Outliers"]),
            "change_point": str(row["Change Point"]),
        }
        for row in expected_replicates.to_dict(orient="records")
    ]
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.control_chart_rows[0].zone = "Changed"


def test_analyze_dls_trend_diagnostics_validates_samples_and_allows_empty_rows():
    result = analyze_dls_trend_diagnostics([_decision_sample("single", 0.20, [])])
    assert result.control_chart_rows == ()
    assert result.replicate_statistics_rows == ()
    with raises(ValueError, match="At least one parsed DLS sample"):
        analyze_dls_trend_diagnostics([])
    with raises(TypeError, match="require parsed samples"):
        analyze_dls_trend_diagnostics([object()])


def test_analyze_dls_forward_scatter_trends_preserves_points_and_relationships():
    samples = [
        _decision_sample("A", 0.20, []),
        _decision_sample("B", 0.21, []),
        _decision_sample("C", 0.22, []),
    ]
    for sample, time, z_average, pdi in zip(
        samples,
        (10.0, 20.0, 30.0),
        (100.0, 160.0, 220.0),
        (0.20, 0.30, 0.40),
    ):
        sample.measurement.angle_summaries = [
            AngleSummary(
                label="Forward 12.8°",
                angle_degrees=12.8,
                position="forward",
                z_average=z_average,
                pdi=pdi,
            )
        ]
        apply_circulation_time(sample.measurement, time, "minutes")

    result = analyze_dls_forward_scatter_trends(samples)
    expected = build_forward_scatter_trend_analysis_from_measurements(samples)

    assert isinstance(result, DLSForwardScatterTrendRead)
    assert [point.sample_name for point in result.points] == ["A", "B", "C"]
    assert [point.circulation_time_minutes for point in result.points] == [10.0, 20.0, 30.0]
    assert result.z_average.pearson_r == expected.z_average.pearson_r
    assert result.z_average.relationship == "strong"
    assert result.z_average.message == expected.z_average.message
    assert "correlation only" in result.z_average.message
    assert result.pdi.correlation == expected.pdi.correlation
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.points[0].sample_name = "Changed"


def test_analyze_dls_forward_scatter_trends_validates_and_preserves_empty_result():
    result = analyze_dls_forward_scatter_trends(
        [_decision_sample("missing time", 0.20, [])]
    )
    assert result.points == ()
    assert "At least 3 valid samples" in result.z_average.message
    with raises(ValueError, match="At least one parsed DLS sample"):
        analyze_dls_forward_scatter_trends([])
    with raises(TypeError, match="require parsed samples"):
        analyze_dls_forward_scatter_trends([object()])


def test_analyze_filtration_follow_up_trends_preserves_points_and_relationships():
    samples = [
        _decision_sample("A", 0.20, []),
        _decision_sample("B", 0.21, []),
        _decision_sample("C", 0.22, []),
    ]
    for index, sample in enumerate(samples, start=1):
        sample.measurement.angle_summaries = [
            AngleSummary(
                label="Forward 12.8°",
                angle_degrees=12.8,
                position="forward",
                z_average=float(index * 60 + 40),
                pdi=float(index) / 10 + 0.1,
            )
        ]
        apply_circulation_time(sample.measurement, index * 10, "minutes")
        apply_filtration_measurement(
            sample.measurement,
            FiltrationMeasurement(
                sample_name=sample.name,
                difficulty_score=float(index),
            ),
        )

    result = analyze_filtration_follow_up_trends(samples)
    expected = build_filtration_trend_analysis(samples)

    assert isinstance(result, FiltrationTrendRead)
    assert [point.sample_name for point in result.points] == ["A", "B", "C"]
    assert [point.difficulty_score for point in result.points] == [1.0, 2.0, 3.0]
    assert result.z_average.method == "Spearman"
    assert result.z_average.correlation == expected.z_average.correlation
    assert result.z_average.relationship == "strong"
    assert result.pdi.message == expected.pdi.message
    assert result.circulation_time.correlation == expected.circulation_time.correlation
    assert "correlation only" in result.circulation_time.message
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.points[0].difficulty_score = 5.0


def test_analyze_filtration_follow_up_trends_validates_and_preserves_empty_result():
    result = analyze_filtration_follow_up_trends(
        [_decision_sample("missing filtration", 0.20, [])]
    )
    assert result.points == ()
    assert "At least 3 valid samples" in result.z_average.message
    with raises(ValueError, match="At least one parsed DLS sample"):
        analyze_filtration_follow_up_trends([])
    with raises(TypeError, match="require parsed DLS samples"):
        analyze_filtration_follow_up_trends([object()])


def test_assess_dls_aggregation_preserves_available_and_unavailable_evidence():
    available = _decision_sample("available", 0.20, [])
    available.measurement.angle_summaries = [
        AngleSummary(
            label="Forward 12.8°",
            angle_degrees=12.8,
            position="forward",
            z_average=453.0,
            primary_peak_nm=420.0,
            replicate_count=3,
        ),
        AngleSummary(
            label="Back 173°",
            angle_degrees=173.0,
            position="back",
            z_average=265.0,
            primary_peak_nm=267.0,
            replicate_count=3,
        ),
    ]
    unavailable = _decision_sample("unavailable", 0.20, [])
    unavailable.measurement.angle_summaries = [
        AngleSummary(label="Back 173°", angle_degrees=173.0, z_average=265.0)
    ]

    result = assess_dls_aggregation([available, unavailable])
    expected = assess_dual_angle_aggregation(available.measurement)

    assert isinstance(result, DLSAggregationRead)
    assert [item.sample_name for item in result.assessments] == [
        "available",
        "unavailable",
    ]
    assessment = result.assessments[0]
    assert assessment.available is True
    assert assessment.aggregation_index == expected.aggregation_index
    assert assessment.forward.z_average_nm == 453.0
    assert assessment.backward.z_average_nm == 265.0
    assert assessment.category == expected.category
    assert assessment.confidence == expected.confidence
    assert [check.to_dict() for check in assessment.checks] == [
        {
            "label": check.label,
            "status": check.status,
            "detail": check.detail,
            "corroborating": check.corroborating,
            "independent_evidence": check.independent_evidence,
        }
        for check in expected.checks
    ]
    assert result.assessments[1].available is False
    assert "needs a forward" in result.assessments[1].summary
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        assessment.category = "Changed"


def test_assess_dls_aggregation_validates_parsed_samples():
    with raises(ValueError, match="At least one parsed DLS sample"):
        assess_dls_aggregation([])
    with raises(TypeError, match="requires parsed samples"):
        assess_dls_aggregation([object()])


def test_summarize_dls_samples_preserves_status_evidence_and_display_rows():
    clean = _decision_sample("clean", 0.12, [])
    flagged = _decision_sample("flagged", 0.35, ["Moderate PDI"])

    result = summarize_dls_samples([clean, flagged])

    assert isinstance(result, DLSSampleSummaries)
    assert [sample.sample_name for sample in result.samples] == ["clean", "flagged"]
    assert result.samples[0].status == "Normal"
    assert result.samples[1].status == "Watch"
    assert result.samples[1].warnings == ("Moderate PDI",)
    assert result.samples[1].review_evidence == "PDI 0.35"
    assert [row.to_dict() for row in result.samples[1].metric_rows] == [
        {"label": "Type", "value": "Distribution Curve"},
        {"label": "Z-Average", "value": "100 nm"},
        {"label": "PDI", "value": "0.35"},
        {"label": "Measurements", "value": "Not found"},
        {"label": "Angles", "value": "Not found"},
        {"label": "Primary Peak", "value": "100 nm"},
        {"label": "Tail >1,000 nm", "value": "0 %"},
        {"label": "Review signals", "value": "Moderate PDI"},
    ]
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.samples[0].status = "Changed"


def test_summarize_dls_samples_preserves_missing_optional_rows_and_validates():
    sample = _decision_sample("missing", 0.12, [])
    sample.metrics["Primary Peak"] = None
    sample.metrics["Tail Index"] = None
    result = summarize_dls_samples([sample])

    assert [row.label for row in result.samples[0].metric_rows] == [
        "Type",
        "Z-Average",
        "PDI",
        "Measurements",
        "Angles",
        "Review signals",
    ]
    assert result.samples[0].metric_rows[-1].value == "No flags"
    with raises(ValueError, match="At least one parsed DLS sample"):
        summarize_dls_samples([])
    with raises(TypeError, match="require parsed samples"):
        summarize_dls_samples([object()])


def test_retrieve_dls_angle_details_preserves_rows_values_and_order():
    first = _decision_sample("first", 0.12, [])
    first.measurement.angle_summaries = [
        AngleSummary(
            label="Forward 12.8°",
            angle_degrees=12.8,
            position="forward",
            count=9,
            replicate_count=3,
            z_average=453.0,
            pdi=0.31,
            max_z_average=470.0,
            primary_peak_nm=420.0,
            d50_nm=415.0,
        ),
        AngleSummary(
            label="Back 173°",
            angle_degrees=173.0,
            position="back",
            count=9,
            replicate_count=3,
            z_average=265.0,
            pdi=0.22,
            primary_peak_nm=267.0,
            d50_nm=260.0,
        ),
    ]
    second = _decision_sample("second", 0.15, [])
    second.measurement.angle_summaries = [
        AngleSummary(label="Back 173°", angle_degrees=173.0, z_average=275.0)
    ]

    result = retrieve_dls_angle_details([first, second])
    expected = build_angle_table([first, second])

    assert isinstance(result, DLSAngleDetails)
    assert [(row.sample_name, row.angle_label) for row in result.rows] == [
        ("first", "Forward 12.8°"),
        ("first", "Back 173°"),
        ("second", "Back 173°"),
    ]
    assert [row.z_average_nm for row in result.rows] == [453.0, 265.0, 275.0]
    assert result.rows[0].replicate_count == 3
    assert result.rows[0].d50_nm == 415.0
    assert len(result.rows) == len(expected)
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.rows[0].angle_label = "Changed"


def test_retrieve_dls_angle_details_validates_and_allows_empty_rows():
    result = retrieve_dls_angle_details([_decision_sample("no angles", 0.12, [])])
    assert result.rows == ()
    with raises(ValueError, match="At least one parsed DLS sample"):
        retrieve_dls_angle_details([])
    with raises(TypeError, match="require parsed samples"):
        retrieve_dls_angle_details([object()])


def test_retrieve_dls_metrics_preserves_established_projection_exactly():
    clean = _decision_sample("clean", 0.12, [])
    flagged = _decision_sample("flagged", 0.35, ["Moderate PDI", "Large tail"])
    flagged.metrics.update(
        {
            "Peak Count": 2,
            "Peak Width Ratio": 1.25,
            "Peak Symmetry": 0.9,
            "Skewness": 0.4,
            "Aggregation Risk": "Watch",
            "Aggregation Index": 0.3,
            "Quality Score": 82.0,
            "Correlogram Noise": 0.02,
        }
    )

    result = retrieve_dls_metrics([clean, flagged])

    assert isinstance(result, DLSMetricsProjection)
    assert [row.sample_name for row in result.rows] == ["clean", "flagged"]
    assert result.rows[1].status == "Watch"
    assert result.rows[1].warnings == ("Moderate PDI", "Large tail")
    assert dls_metrics_dataframe(result).equals(build_metrics_table([clean, flagged]))
    assert result.to_dict()["rows"][1]["warnings"] == ["Moderate PDI", "Large tail"]
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.rows[0].status = "Changed"


def test_retrieve_dls_metrics_validates_parsed_samples():
    with raises(ValueError, match="At least one parsed DLS sample"):
        retrieve_dls_metrics([])
    with raises(TypeError, match="require parsed samples"):
        retrieve_dls_metrics([object()])


def _distribution_sample(
    name: str,
    diameters: list[float],
    intensity: list[float],
    *,
    volume: list[float] | None = None,
) -> ParsedSample:
    sample = _decision_sample(name, 0.12, [])
    data = {"Diameter": diameters, "Intensity": intensity}
    if volume is not None:
        data["Volume"] = volume
    sample.data = pd.DataFrame(data)
    sample.metrics.update(
        {
            "Diameter Column": "Diameter",
            "Intensity Column": "Intensity",
            "Volume Column": "Volume" if volume is not None else None,
            "Number Column": None,
        }
    )
    return sample


def test_retrieve_dls_distributions_preserves_points_peaks_and_signal_order():
    reference = _distribution_sample(
        "reference",
        [100, -1, 10, 1000, 50],
        [50, 20, 10, 5, -2],
        volume=[40, 10, 5, 2, -1],
    )
    comparison = _distribution_sample(
        "comparison", [9, 110, 900], [5, 20, 10]
    )

    result = retrieve_dls_distributions([reference, comparison])

    assert isinstance(result, DLSDistributionProjection)
    assert result.available_signals == ("Intensity", "Volume")
    assert [sample.sample_name for sample in result.samples] == [
        "reference",
        "comparison",
    ]
    assert [series.signal for series in result.samples[0].series] == [
        "Intensity",
        "Volume",
        "Number",
    ]
    intensity = result.samples[0].series_for("Intensity")
    assert intensity is not None
    assert intensity.columns_identified is True
    assert [(point.diameter_nm, point.signal_value) for point in intensity.points] == [
        (10.0, 10.0),
        (100.0, 50.0),
        (1000.0, 5.0),
    ]
    assert [(peak.diameter_nm, peak.signal_value) for peak in intensity.peaks] == [
        (100.0, 50.0)
    ]
    assert result.samples[0].series_for("Number").signal_column_identified is False
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        intensity.points[0].diameter_nm = 20.0


def test_distribution_shell_helpers_preserve_normalization_and_nearest_delta():
    reference = retrieve_dls_distributions(
        [_distribution_sample("reference", [100, 10, 1000], [50, 10, 5])]
    ).samples[0].series_for("Intensity")
    comparison = retrieve_dls_distributions(
        [_distribution_sample("comparison", [9, 110, 900], [5, 20, 10])]
    ).samples[0].series_for("Intensity")
    assert reference is not None
    assert comparison is not None

    normalized = distribution_series_dataframe(reference, normalize=True)
    assert normalized.to_dict(orient="list") == {
        "Diameter": [10.0, 100.0, 1000.0],
        "Signal": [20.0, 100.0, 10.0],
    }
    difference = distribution_difference_dataframe(comparison, reference)
    assert difference.to_dict(orient="list") == {
        "Diameter": [9.0, 110.0, 900.0],
        "Delta": [5.0, 0.0, 40.0],
    }


def test_retrieve_dls_distributions_preserves_fallback_and_validates_samples():
    sample = _distribution_sample("missing", [10], [1])
    sample.metrics.update(
        {
            "Diameter Column": None,
            "Intensity Column": None,
            "Volume Column": None,
            "Number Column": None,
        }
    )
    result = retrieve_dls_distributions([sample])
    assert result.available_signals == ("Intensity",)
    assert result.samples[0].series_for("Intensity").points == ()
    with raises(ValueError, match="At least one parsed DLS sample"):
        retrieve_dls_distributions([])
    with raises(TypeError, match="require parsed samples"):
        retrieve_dls_distributions([object()])


def test_retrieve_dls_raw_evidence_preserves_tables_metadata_and_sources():
    sample = _distribution_sample("Lot 1", [100, 10], [50, 5])
    sample.data["Comment"] = ["primary", "small"]
    sample.metadata = {"Instrument": "Zetasizer", "Operator": "Ada"}
    sample.source_text = "fallback source text"
    source = DLSUploadFileRead(
        file_name="Lot 1 intensity.csv",
        file_type="Intensity distribution",
        source_text="Diameter,Intensity\n10,5\n100,50\n",
        error=None,
    )
    group = DLSUploadGroupRead(
        lot="Lot 1",
        status="Ready",
        summary_files=(),
        intensity_files=(source,),
        correlogram_files=(),
        files=(source,),
    )

    result = retrieve_dls_raw_evidence([sample], groups=(group,))

    assert isinstance(result, DLSRawEvidence)
    assert result.samples[0].point_table.columns == (
        "Diameter",
        "Intensity",
        "Comment",
    )
    assert result.samples[0].point_table.rows == (
        (100, 50, "primary"),
        (10, 5, "small"),
    )
    assert [field.to_dict() for field in result.samples[0].metadata] == [
        {"field": "Instrument", "value": "Zetasizer"},
        {"field": "Operator", "value": "Ada"},
    ]
    assert result.samples[0].source_text == "fallback source text"
    assert result.source_files[0].to_dict() == {
        "lot": "Lot 1",
        "file_name": "Lot 1 intensity.csv",
        "file_type": "Intensity distribution",
        "source_text": "Diameter,Intensity\n10,5\n100,50\n",
        "error": None,
    }
    reconstructed = raw_point_table_dataframe(result.samples[0].point_table)
    assert reconstructed.to_csv(index=False) == sample.data.to_csv(index=False)
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.samples[0].sample_name = "Changed"


def test_retrieve_dls_raw_evidence_preserves_fallback_and_validates_inputs():
    sample = _distribution_sample("Lot 1", [10], [5])
    sample.metadata = {}
    sample.source_text = "x" * 12001
    result = retrieve_dls_raw_evidence([sample])

    assert result.source_files == ()
    assert result.samples[0].metadata == ()
    assert len(result.samples[0].source_text[:12000]) == 12000
    with raises(ValueError, match="At least one parsed DLS sample"):
        retrieve_dls_raw_evidence([])
    with raises(TypeError, match="requires parsed samples"):
        retrieve_dls_raw_evidence([object()])
    with raises(TypeError, match="upload-group diagnostics"):
        retrieve_dls_raw_evidence([sample], groups=(object(),))


def test_retrieve_dls_correlograms_preserves_series_points_noise_and_order():
    first = _decision_sample("first", 0.12, [])
    first.measurement.correlogram = [
        {"delay_time": 0.1, "correlation": 0.98, "replicate": 1.0},
        {"delay_time": 1.0, "correlation": 0.75, "replicate": 1.0},
    ]
    first.measurement.derived_metrics.correlogram_noise_score = 0.025
    empty = _decision_sample("empty", 0.12, [])
    second = _decision_sample("second", 0.12, [])
    second.measurement.correlogram = [
        {"delay_time": 0.2, "correlation": 0.9, "replicate": 2.0}
    ]

    result = retrieve_dls_correlograms([first, empty, second])

    assert isinstance(result, DLSCorrelograms)
    assert [series.sample_name for series in result.series] == ["first", "second"]
    assert result.series[0].noise_score == 0.025
    assert [point.to_dict() for point in result.series[0].points] == [
        {"delay_time": 0.1, "correlation": 0.98, "replicate": 1.0},
        {"delay_time": 1.0, "correlation": 0.75, "replicate": 1.0},
    ]
    assert result.series[1].noise_score is None
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    with raises(FrozenInstanceError):
        result.series[0].noise_score = 1.0


def test_retrieve_dls_correlograms_allows_empty_result_and_validates_samples():
    result = retrieve_dls_correlograms([_decision_sample("empty", 0.12, [])])
    assert result.series == ()
    with raises(ValueError, match="At least one parsed DLS sample"):
        retrieve_dls_correlograms([])
    with raises(TypeError, match="require parsed samples"):
        retrieve_dls_correlograms([object()])


def test_analyze_dls_dataset_validates_local_file_selection(tmp_path):
    with raises(ValueError, match="Select at least one"):
        analyze_dls_dataset([])

    with raises(FileNotFoundError, match="DLS file not found"):
        analyze_dls_dataset([tmp_path / "missing.csv"])

    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("This is not an instrument export.", encoding="utf-8")
    with raises(ValueError, match="No supported DLS summary or intensity"):
        analyze_dls_dataset([unrelated])


def test_analyze_chromatography_csv_returns_typed_tables_and_reasoning():
    result = analyze_chromatography_source(
        Path("sample_data/chromatography/mass_balance_demo.csv"),
        label="Mass balance run",
    )

    assert isinstance(result, ChromatographyAnalysisResult)
    assert result.source_kind == "chromatography_csv"
    assert result.experiment.label == "Mass balance run"
    assert result.experiment.technique == "HPLC"
    assert len(result.measurements) == 6
    assert result.assessment is not None
    assert result.assessment.total_area_change_percent == approx(-24.710, abs=0.001)
    assert [point.timepoint for point in result.trends] == ["T0", "T1", "T2"]
    assert result.trends[-1].change_vs_start_percent == approx(-24.710, abs=0.001)
    assert "Degradation into detected impurities" in result.hypotheses
    assert result.to_dict()["api_version"] == AGENT_API_VERSION
    restored = result.restore_experiment()
    restored.label = "Caller mutation"
    assert result.restore_experiment().label == "Mass balance run"


def test_analyze_chromatography_source_rejects_unsupported_suffix(tmp_path):
    source = tmp_path / "chromatography.txt"
    source.write_text("not supported", encoding="utf-8")
    with raises(ValueError, match="CSV or OpenLab"):
        analyze_chromatography_source(source)


def test_analyze_filtration_csv_returns_immutable_normalized_summaries():
    from io import StringIO

    result = analyze_filtration_csv(
        StringIO(
            "sample name,difficulty score,filtration time,filtration time unit,pressure,pressure unit,filter type,clogging observed,notes\n"
            "Lot 1,4,30,seconds,10,psi,PES,yes,slow\n"
            "Lot 2,7,1,minutes,1,bar,PES,no,bad score\n"
        ),
        source_name="filtration.csv",
    )

    assert isinstance(result, FiltrationImportRead)
    assert len(result.measurements) == 1
    summary = result.measurements[0]
    assert summary.sample_name == "Lot 1"
    assert summary.filtration_time_minutes == 0.5
    assert summary.pressure_unit == "psi"
    assert summary.pressure_kpa == approx(68.948, abs=0.001)
    assert summary.clogging_observed is True
    assert any("difficulty score" in warning for warning in result.warnings)
    restored = result.restore_measurements()
    restored[0].sample_name = "Caller mutation"
    assert result.restore_measurements()[0].sample_name == "Lot 1"
    assert result.to_dict()["api_version"] == AGENT_API_VERSION


def test_analyze_filtration_csv_preserves_column_diagnostics():
    from io import StringIO

    result = analyze_filtration_csv(
        StringIO("sample,pressure,unexpected\nLot 1,10,value\n"),
        source_name="bad.csv",
    )

    assert result.measurements == ()
    assert result.missing_columns == ("difficulty_score",)
    assert result.unsupported_columns == ("unexpected",)
    assert "missing required columns" in result.errors[0].lower()


def test_save_experiment_to_memory_can_use_injected_store():
    experiment = Experiment(
        experiment_id="exp-1",
        label="Stress study",
        technique="HPLC",
        instrument="Chromatography",
        metadata={
            "hypotheses": ["Degradation pathway"],
            "recommendations": ["Run orthogonal purity method"],
        },
    )
    store = RecordingStore()

    save_experiment_to_memory(
        experiment,
        human_note="Discuss with analytical team.",
        project_id="project-1",
        tags=["screening"],
        store=store,
    )

    assert store.experiments == [(experiment, "project-1", ["screening"])]
    assert store.hypotheses[0][0] == "Degradation pathway"
    assert store.recommendations[0][0] == "Run orthogonal purity method"
    assert store.notes[0][0] == "Discuss with analytical team."


def test_capability_registry_exposes_stable_scientific_workflow_names():
    capabilities = list_capabilities()

    assert isinstance(capabilities, tuple)
    assert [capability.name for capability in capabilities] == [
        "describe_platform",
        "describe_agent_access",
        "import_dls_experiment",
        "analyze_dls_dataset",
        "analyze_dls_uploads",
        "rank_dls_decisions",
        "compose_dls_narrative",
        "summarize_dls_health",
        "analyze_dls_trend_diagnostics",
        "analyze_dls_forward_scatter_trends",
        "analyze_filtration_follow_up_trends",
        "assess_dls_aggregation",
        "summarize_dls_samples",
        "retrieve_dls_angle_details",
        "retrieve_dls_metrics",
        "retrieve_dls_distributions",
        "retrieve_dls_raw_evidence",
        "retrieve_dls_correlograms",
        "import_chromatography_experiment",
        "analyze_chromatography_source",
        "analyze_filtration_csv",
        "generate_observations",
        "list_experiments",
        "compare_experiments",
        "find_related_experiments",
        "retrieve_history_overview",
        "retrieve_experiment",
        "retrieve_experiment_summary",
        "investigate_experiment",
        "produce_experiment_brief",
        "retrieve_related_context",
        "retrieve_research_journal",
        "add_scientific_note",
        "save_experiment_history",
        "save_scientific_memory",
    ]
    assert all(capability.version == AGENT_API_VERSION for capability in capabilities)
    assert all("Human UI" in capability.caller_types for capability in capabilities)
    assert all(
        "Future API" in capability.caller_types
        for capability in capabilities
        if capability.name not in {"add_scientific_note", "save_experiment_history"}
    )
    assert get_capability("add_scientific_note").caller_types == ("Human UI", "CLI")
    assert get_capability("save_experiment_history").caller_types == ("Human UI", "CLI")
    narrative = get_capability("compose_dls_narrative")
    assert narrative.handler is compose_dls_narrative
    assert narrative.caller_types == ("Human UI", "CLI", "Future API")
    health = get_capability("summarize_dls_health")
    assert health.handler is summarize_dls_health
    assert health.caller_types == ("Human UI", "CLI", "Future API")
    diagnostics = get_capability("analyze_dls_trend_diagnostics")
    assert diagnostics.handler is analyze_dls_trend_diagnostics
    assert diagnostics.caller_types == ("Human UI", "CLI", "Future API")
    forward_trends = get_capability("analyze_dls_forward_scatter_trends")
    assert forward_trends.handler is analyze_dls_forward_scatter_trends
    assert forward_trends.caller_types == ("Human UI", "CLI", "Future API")
    filtration_trends = get_capability("analyze_filtration_follow_up_trends")
    assert filtration_trends.handler is analyze_filtration_follow_up_trends
    assert filtration_trends.caller_types == ("Human UI", "CLI", "Future API")
    aggregation = get_capability("assess_dls_aggregation")
    assert aggregation.handler is assess_dls_aggregation
    assert aggregation.caller_types == ("Human UI", "CLI", "Future API")
    sample_summaries = get_capability("summarize_dls_samples")
    assert sample_summaries.handler is summarize_dls_samples
    assert sample_summaries.caller_types == ("Human UI", "CLI", "Future API")
    angle_details = get_capability("retrieve_dls_angle_details")
    assert angle_details.handler is retrieve_dls_angle_details
    assert angle_details.caller_types == ("Human UI", "CLI", "Future API")
    metrics = get_capability("retrieve_dls_metrics")
    assert metrics.handler is retrieve_dls_metrics
    assert metrics.caller_types == ("Human UI", "CLI", "Future API")
    distributions = get_capability("retrieve_dls_distributions")
    assert distributions.handler is retrieve_dls_distributions
    assert distributions.caller_types == ("Human UI", "CLI", "Future API")
    raw_evidence = get_capability("retrieve_dls_raw_evidence")
    assert raw_evidence.handler is retrieve_dls_raw_evidence
    assert raw_evidence.caller_types == ("Human UI", "CLI", "Future API")
    correlograms = get_capability("retrieve_dls_correlograms")
    assert correlograms.handler is retrieve_dls_correlograms
    assert correlograms.caller_types == ("Human UI", "CLI", "Future API")


def test_capability_registry_resolves_existing_entry_points_without_wrapping_them():
    capability = get_capability("retrieve_experiment_summary")

    assert capability.handler is build_experiment_snapshot
    assert capability.purpose == "Return a stable read-only summary of an experiment."

    persisted = get_capability("retrieve_experiment")
    assert persisted.handler is retrieve_experiment

    investigation = get_capability("investigate_experiment")
    assert investigation.handler is investigate_experiment

    brief = get_capability("produce_experiment_brief")
    assert brief.handler is produce_experiment_brief

    context = get_capability("retrieve_related_context")
    assert context.handler is retrieve_related_context

    journal = get_capability("retrieve_research_journal")
    assert journal.handler is retrieve_research_journal

    note = get_capability("add_scientific_note")
    assert note.handler is add_scientific_note

    history_save = get_capability("save_experiment_history")
    assert history_save.handler is save_experiment_history

    chromatography = get_capability("analyze_chromatography_source")
    assert chromatography.handler is analyze_chromatography_source
    assert "Agent" not in chromatography.caller_types

    filtration = get_capability("analyze_filtration_csv")
    assert filtration.handler is analyze_filtration_csv
    assert "Agent" not in filtration.caller_types

    observations = get_capability("generate_observations")
    assert observations.handler is generate_observations

    dls_uploads = get_capability("analyze_dls_uploads")
    assert dls_uploads.handler is analyze_dls_uploads
    assert "Agent" not in dls_uploads.caller_types

    dls_ranking = get_capability("rank_dls_decisions")
    assert dls_ranking.handler is rank_dls_decisions
    assert "Agent" not in dls_ranking.caller_types


def test_capability_registry_rejects_unknown_names():
    try:
        get_capability("launch_autonomous_lab")
    except KeyError as error:
        assert "Unknown LabAssistant capability" in str(error)
    else:
        raise AssertionError("Unknown capabilities must not resolve")
