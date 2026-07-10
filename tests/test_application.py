from pathlib import Path

from pytest import approx, raises

from labassistant.application import (
    AGENT_API_VERSION,
    APP_DIRECTION,
    HUMAN_APP_SURFACE,
    analyze_dls_dataset,
    agent_access_policy,
    app_manifest,
    build_experiment_snapshot,
    dls_experiment_from_samples,
    get_capability,
    list_capabilities,
    retrieve_experiment,
    save_experiment_to_memory,
)
from labassistant.models import Experiment, Measurement, MeasurementMetadata, Observation
from labassistant.history import save_experiment
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
        "retrieve_experiment",
        "retrieve_experiment_summary",
        "save_scientific_memory",
    ]
    assert all(capability.version == AGENT_API_VERSION for capability in capabilities)
    assert all("Human UI" in capability.caller_types for capability in capabilities)
    assert all("Future API" in capability.caller_types for capability in capabilities)


def test_capability_registry_resolves_existing_entry_points_without_wrapping_them():
    capability = get_capability("retrieve_experiment_summary")

    assert capability.handler is build_experiment_snapshot
    assert capability.purpose == "Return a stable read-only summary of an experiment."

    persisted = get_capability("retrieve_experiment")
    assert persisted.handler is retrieve_experiment


def test_capability_registry_rejects_unknown_names():
    try:
        get_capability("launch_autonomous_lab")
    except KeyError as error:
        assert "Unknown LabAssistant capability" in str(error)
    else:
        raise AssertionError("Unknown capabilities must not resolve")
