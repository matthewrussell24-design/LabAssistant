from __future__ import annotations

from labassistant.context_engine import (
    ENTITY_HYPOTHESIS,
    ENTITY_NOTE,
    ENTITY_OBSERVATION,
    ENTITY_RECOMMENDATION,
    ENTITY_SOURCE_FILE,
    ContextRetriever,
    KnowledgeStore,
    ResearchJournal,
)
from labassistant.models import ChromatographyMeasurement, Experiment, Observation


def make_experiment() -> Experiment:
    return Experiment(
        experiment_id="exp-hplc-1",
        label="Phenyl hexyl HPLC run",
        instrument="Agilent 1290 HPLC",
        technique="HPLC",
        source_path="/data/HPLC Test 1.olax",
        measurements=[
            ChromatographyMeasurement(
                sample_name="Sample A",
                injection_id="3",
                method_name="Phenyl Hexyl column 50C",
                source_files=["Data/Injection_003.dx"],
                total_area=1000.0,
            )
        ],
        observations=[
            Observation(
                label="Chromatogram signal available",
                category="chromatography_import",
                evidence="1 recognized detector signal file located.",
                severity="normal",
                confidence="high",
                source_type="openlab_olax",
            ),
            Observation(
                label="Missing peak table",
                category="data_completeness",
                evidence="No result/peak table file was detected.",
                severity="watch",
                confidence="medium",
                recommendation="Export a peak table for quantitative analysis.",
            ),
        ],
        unsupported_sections=["Raw chromatogram signal traces are located but not decoded."],
    )


def test_knowledge_store_persists_experiment_memory(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    store.add_experiment(make_experiment(), project_id="stability", tags=["phase8", "openlab"])

    observations = store.list_items(entity_type=ENTITY_OBSERVATION)
    recommendations = store.list_items(entity_type=ENTITY_RECOMMENDATION)
    source_files = store.list_items(entity_type=ENTITY_SOURCE_FILE)

    assert {observation.title for observation in observations} == {
        "Chromatogram signal available",
        "Missing peak table",
    }
    assert recommendations[0].text == "Export a peak table for quantitative analysis."
    assert {source.title for source in source_files} == {"HPLC Test 1.olax", "Injection_003.dx"}


def test_context_retriever_returns_compact_packet(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    store.add_experiment(make_experiment(), project_id="stability", tags=["phase8", "openlab"])
    store.add_note(
        "Operator noted the detector trace looked normal but integration export was not included.",
        title="Run note",
        experiment_id="exp-hplc-1",
        project_id="stability",
        tags=["openlab", "integration"],
    )
    store.add_hypothesis(
        "The experiment can be interpreted qualitatively, but quantitative mass balance needs peak areas.",
        experiment_id="exp-hplc-1",
        project_id="stability",
        tags=["openlab", "mass_balance"],
    )

    packet = ContextRetriever(store).retrieve("Can the OpenLab HPLC run support mass balance interpretation?")

    assert packet.relevant_experiments[0].title == "Phenyl hexyl HPLC run"
    assert any(item.title == "Missing peak table" for item in packet.relevant_observations)
    assert any("peak table" in item.text.lower() for item in packet.recommendations)
    assert any(item.entity_type == ENTITY_NOTE for item in packet.related_notes)
    assert any(item.entity_type == ENTITY_HYPOTHESIS for item in packet.hypotheses)
    assert packet.missing_information
    assert packet.confidence == "medium"
    assert "deterministic keyword/tag retrieval" in packet.caveats[-1]


def test_context_retriever_handles_empty_memory(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")

    packet = ContextRetriever(store).retrieve("What happened in the DLS run?")

    assert packet.relevant_experiments == []
    assert packet.confidence == "low"
    assert packet.missing_information == []
    assert "No matching local memory" in packet.caveats[0]


def test_research_journal_groups_saved_experiment_and_exports_markdown(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    experiment = make_experiment()
    store.add_experiment(experiment, project_id="stability", tags=["openlab", "weekend"])
    store.add_hypothesis(
        "Quantitative mass balance needs exported peak areas.",
        experiment_id=experiment.experiment_id,
        instrument_id=experiment.instrument,
        tags=["openlab", "mass_balance"],
    )
    store.add_note(
        "Column backpressure was normal.",
        title="Operator note",
        experiment_id=experiment.experiment_id,
        instrument_id=experiment.instrument,
        tags=["openlab"],
    )

    journal = ResearchJournal(store)
    entries = journal.entries(keyword="mass balance", tag="openlab", instrument="Agilent", sample="Sample A")
    markdown = journal.export_markdown(keyword="mass balance", tag="openlab")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "Phenyl hexyl HPLC run"
    assert any("Missing peak table" in observation for observation in entry.key_observations)
    assert entry.hypotheses == ["Quantitative mass balance needs exported peak areas."]
    assert "Column backpressure was normal." in entry.notes
    assert "HPLC Test 1.olax" in " ".join(entry.source_files)
    assert "# LabAssistant Research Journal" in markdown
    assert "## Phenyl hexyl HPLC run" in markdown
    assert "Quantitative mass balance needs exported peak areas." in markdown


def test_research_journal_includes_standalone_manual_notes(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    store.add_note(
        "Weekend review: compare DLS aggregation with HPLC missing area.",
        title="Weekend synthesis",
        tags=["weekend", "dls"],
    )

    entries = ResearchJournal(store).entries(tag="weekend", keyword="aggregation")

    assert len(entries) == 1
    assert entries[0].title == "Weekend synthesis"
    assert entries[0].notes == ["Weekend review: compare DLS aggregation with HPLC missing area."]


def test_research_journal_preserves_multiple_default_titled_hypotheses(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    experiment = make_experiment()
    store.add_experiment(experiment, tags=["openlab"])
    hypotheses = [
        "Degradation into detected impurities",
        "Degradation into unknown chromatographic species",
        "Method instability or integration error",
        "Injection reproducibility issue",
    ]
    for hypothesis in hypotheses:
        store.add_hypothesis(hypothesis, experiment_id=experiment.experiment_id, tags=["openlab"])

    entries = ResearchJournal(store).entries(keyword="degradation", tag="openlab")

    assert len(entries) == 1
    assert entries[0].hypotheses == hypotheses
