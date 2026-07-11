import json
from pathlib import Path

from pytest import approx, raises

from labassistant.application import (
    AGENT_API_VERSION,
    APP_DIRECTION,
    HUMAN_APP_SURFACE,
    ExperimentListing,
    ExperimentComparison,
    ExperimentInvestigation,
    ChromatographyRestoreResult,
    ChromatographyAnalysisResult,
    HistoryOverview,
    RelatedExperiments,
    RelatedScientificContext,
    ResearchJournalRead,
    ScientificNoteReceipt,
    add_scientific_note,
    analyze_dls_dataset,
    analyze_chromatography_source,
    compare_experiments,
    agent_access_policy,
    app_manifest,
    build_experiment_snapshot,
    dls_experiment_from_samples,
    find_related_experiments,
    investigate_experiment,
    get_capability,
    list_capabilities,
    list_experiments,
    retrieve_history_overview,
    retrieve_related_context,
    retrieve_research_journal,
    restore_chromatography_experiment,
    restore_dls_experiment,
    retrieve_experiment,
    save_experiment_to_memory,
)
from labassistant.models import (
    ChromatogramTrace,
    ChromatographyMeasurement,
    ChromatographyPeak,
    Experiment,
    Measurement,
    MeasurementMetadata,
    Observation,
)
from labassistant.history import (
    ExperimentRecordNotFoundError,
    MalformedExperimentRecordError,
    save_experiment,
)
from labassistant.context_engine import KnowledgeStore
from labassistant.view_models import ParsedSample


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
        "import_chromatography_experiment",
        "analyze_chromatography_source",
        "list_experiments",
        "compare_experiments",
        "find_related_experiments",
        "retrieve_history_overview",
        "retrieve_experiment",
        "retrieve_experiment_summary",
        "investigate_experiment",
        "retrieve_related_context",
        "retrieve_research_journal",
        "add_scientific_note",
        "save_scientific_memory",
    ]
    assert all(capability.version == AGENT_API_VERSION for capability in capabilities)
    assert all("Human UI" in capability.caller_types for capability in capabilities)
    assert all(
        "Future API" in capability.caller_types
        for capability in capabilities
        if capability.name != "add_scientific_note"
    )
    assert get_capability("add_scientific_note").caller_types == ("Human UI", "CLI")


def test_capability_registry_resolves_existing_entry_points_without_wrapping_them():
    capability = get_capability("retrieve_experiment_summary")

    assert capability.handler is build_experiment_snapshot
    assert capability.purpose == "Return a stable read-only summary of an experiment."

    persisted = get_capability("retrieve_experiment")
    assert persisted.handler is retrieve_experiment

    investigation = get_capability("investigate_experiment")
    assert investigation.handler is investigate_experiment

    context = get_capability("retrieve_related_context")
    assert context.handler is retrieve_related_context

    journal = get_capability("retrieve_research_journal")
    assert journal.handler is retrieve_research_journal

    note = get_capability("add_scientific_note")
    assert note.handler is add_scientific_note

    chromatography = get_capability("analyze_chromatography_source")
    assert chromatography.handler is analyze_chromatography_source
    assert "Agent" not in chromatography.caller_types


def test_capability_registry_rejects_unknown_names():
    try:
        get_capability("launch_autonomous_lab")
    except KeyError as error:
        assert "Unknown LabAssistant capability" in str(error)
    else:
        raise AssertionError("Unknown capabilities must not resolve")
