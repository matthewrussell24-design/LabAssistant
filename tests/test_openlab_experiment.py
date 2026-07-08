import zipfile
from pathlib import Path

from labassistant.importers.openlab_olax import build_experiment_from_olax, inspect_openlab_olax
from labassistant.investigator import investigate
from labassistant.models import Experiment


def make_full_olax(path: Path) -> None:
    sequence_xml = """
    <Sequence>
      <SequenceName>Stability run</SequenceName>
      <Operator>MT</Operator>
      <Injection>
        <InjectionOrder>1</InjectionOrder>
        <SampleName>Blank 1</SampleName>
        <Method>HPLC_A</Method>
        <RunTimeMin>10</RunTimeMin>
      </Injection>
      <Injection>
        <InjectionOrder>2</InjectionOrder>
        <SampleName>Standard 1</SampleName>
        <Method>HPLC_A</Method>
        <RunTimeMin>10</RunTimeMin>
      </Injection>
      <Injection>
        <InjectionOrder>3</InjectionOrder>
        <SampleName>Sample A</SampleName>
        <Method>HPLC_A</Method>
        <RunTimeMin>10</RunTimeMin>
      </Injection>
    </Sequence>
    """
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Sequence/sequence.xml", sequence_xml)
        archive.writestr("Data/Injection_001/DAD1A.CH", b"\x01\x02raw")
        archive.writestr("Data/Injection_002/DAD1A.CH", b"\x01\x02raw")
        archive.writestr("Data/Injection_003/DAD1A.CH", b"\x01\x02raw")
        archive.writestr("Results/peak_table.csv", "sample,peak,area\nSample A,parent,1000\n")
        archive.writestr("Method/acqmethod.m", b"acq")
        archive.writestr("Method/processing_method.pmd", b"proc")
        archive.writestr("Audit/audittrail.xml", "<Audit/>")


def test_build_experiment_from_olax(tmp_path):
    fixture = tmp_path / "HPLC Test 1.olax"
    make_full_olax(fixture)

    experiment = build_experiment_from_olax(fixture)

    assert isinstance(experiment, Experiment)
    assert experiment.instrument == "Agilent OpenLab CDS"
    assert experiment.technique == "HPLC"
    assert experiment.label == "Stability run"
    assert len(experiment.measurements) == 3
    assert experiment.metadata["injection_count"] == 3
    assert experiment.metadata["detector_files"]  # DAD1A.CH recognized
    labels = [o.label for o in experiment.observations]
    assert "Chromatogram signal available" in labels
    assert "Peak table available" in labels
    assert "Acquisition method available" in labels
    assert "Audit trail available" in labels
    assert "Blank injections detected" in labels
    assert "Standards detected" in labels
    assert "Sample injections detected" in labels
    # processing method IS present here, so no gap
    assert "Processing method missing" not in labels


def test_full_experiment_is_interpretable(tmp_path):
    fixture = tmp_path / "HPLC Test 1.olax"
    make_full_olax(fixture)

    experiment = build_experiment_from_olax(fixture)
    report = investigate(experiment)

    assert report.is_interpretable is True
    assert report.experiment_id == experiment.experiment_id


def test_unknown_detector_and_processing_gap(tmp_path):
    fixture = tmp_path / "HPLC test 2.olax"
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("sequence.csv", "sample_name,injection_number,method\nSample A,1,M\n")
        # signal-like name but unrecognized container/extension
        archive.writestr("data/chromatogram_001.rawblob", b"\x00\x01\x02")

    result = inspect_openlab_olax(fixture)
    labels = [o.label for o in result.observations]

    assert result.unknown_detector_files == ["data/chromatogram_001.rawblob"]
    assert "Unknown detector file" in labels
    assert "Processing method missing" in labels
    assert "Missing peak table" in labels
    # unsupported sections are reported, not silently dropped
    assert any("not decoded" in section for section in result.unsupported_sections)


def test_experiment_to_dict_roundtrip(tmp_path):
    fixture = tmp_path / "HPLC Test 1.olax"
    make_full_olax(fixture)

    experiment = build_experiment_from_olax(fixture)
    payload = experiment.to_dict()

    assert payload["instrument"] == "Agilent OpenLab CDS"
    assert len(payload["measurements"]) == 3
    assert isinstance(payload["observations"], list)
    assert payload["observations"][0]["label"]
