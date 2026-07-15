from __future__ import annotations

import zipfile

import pandas as pd

from labassistant.application import (
    analyze_chromatography_source,
    chromatography_experiment_from_preview,
    dls_experiment_from_samples,
)
from labassistant.models import (
    ChromatographyMeasurement,
    MassBalanceAssessment,
    Measurement,
    MeasurementFlag,
    MeasurementMetadata,
    Observation,
    SummaryMetrics,
)
from labassistant.view_models import ParsedSample


def make_sample() -> ParsedSample:
    return ParsedSample(
        name="Lot 1",
        file_name="lot1.csv",
        data=pd.DataFrame(),
        metadata={},
        metrics={
            "Data Type": "DLS",
            "Z-Average": 125.0,
            "PDI": 0.42,
            "Secondary Peak": None,
            "Tail Index": None,
            "Width Ratio": None,
            "Aggregation Index": None,
            "Correlogram Noise": None,
        },
        warnings=["Moderate PDI"],
        source_text="",
        measurement=Measurement(
            metadata=MeasurementMetadata(sample_name="Lot 1", source_files=["lot1.csv"]),
            summary_metrics=SummaryMetrics(z_average=125.0, pdi=0.42),
            flags=[MeasurementFlag(label="Moderate PDI")],
        ),
    )


def test_dls_samples_become_memory_experiment():
    experiment = dls_experiment_from_samples(
        [make_sample()],
        label="DLS Run A",
        source_files=["lot1.csv"],
    )

    assert experiment.label == "DLS Run A"
    assert experiment.technique == "DLS"
    assert experiment.measurements[0].sample_name == "Lot 1"
    assert experiment.metadata["source_files"] == ["lot1.csv"]
    assert [observation.label for observation in experiment.observations] == ["High variability"]


def test_chromatography_preview_becomes_memory_experiment_with_hypotheses():
    preview = {
        "measurements": [ChromatographyMeasurement(sample_name="Sample A", injection_id="1")],
        "assessment": MassBalanceAssessment(sample_name="Sample A"),
        "observations": [
            Observation(
                label="Unknown peak appeared",
                category="mass_balance",
                evidence="Unknown area is 2.1%.",
                severity="watch",
            )
        ],
        "hypotheses": ["Degradation into unknown chromatographic species"],
    }

    experiment = chromatography_experiment_from_preview(
        preview,
        label="HPLC Run A",
        source_name="hplc.csv",
    )

    assert experiment.label == "HPLC Run A"
    assert experiment.technique == "HPLC"
    assert experiment.source_path == "hplc.csv"
    assert experiment.metadata["hypotheses"] == ["Degradation into unknown chromatographic species"]
    assert experiment.unsupported_sections == ["Chromatography CSV import does not include raw detector signal traces."]


def test_openlab_olax_preview_becomes_memory_experiment(tmp_path):
    fixture = tmp_path / "OpenLab.olax"
    acaml = """
    <ACAML>
      <InjectionMetaData
        InjectionId="0ed54be7-8ef9-4d0e-8740-3a353d0a2816"
        SampleName="Blank"
        AcqMethodName="Method A"
        RawDataFileName="2026-07-02 12-23-03-04-00-01.dx" />
    </ACAML>
    """
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("Run.rslt%5cRun.acaml", acaml)
        archive.writestr("Run.rslt%5c2026-07-02+12-23-03-04-00-01.dx", b"PK")

    result = analyze_chromatography_source(fixture, label="OpenLab Run")
    experiment = result.restore_experiment()

    assert result.source_kind == "openlab_olax"
    assert experiment.label == "OpenLab Run"
    assert experiment.source_path == fixture.name
    assert experiment.technique == "HPLC"
    assert len(experiment.measurements) == 1
    assert experiment.measurements[0].sample_name == "Blank"
    assert "Chromatogram signal available" in [observation.label for observation in experiment.observations]
