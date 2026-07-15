from labassistant.dls_evidence import (
    DLSSampleEvidence,
    DLSWorkspaceEvidence,
)
from labassistant.view_models import (
    ParsedSample,
    build_metrics_table,
    parse_uploaded_file,
    sample_status,
)


class FakeUpload:
    def __init__(self, name: str, text: str):
        self.name = name
        self._content = text.encode("utf-8")
        self._position = 0

    def seek(self, position: int) -> None:
        self._position = position

    def read(self) -> bytes:
        content = self._content[self._position :]
        self._position = len(self._content)
        return content


def test_parse_uploaded_file_returns_measurement_backed_dashboard_sample():
    upload = FakeUpload(
        "sample_a.csv",
        """Sample Name,Sample A
PDI,0.31

Diameter (nm),Intensity (%)
50,5
100,100
200,10
""",
    )

    sample = parse_uploaded_file(upload)
    metrics = build_metrics_table([sample])

    assert sample.name == "Sample A"
    assert sample.measurement.sample_name == "Sample A"
    assert sample_status(sample) == "Watch"
    assert metrics.loc[0, "Sample"] == "Sample A"
    assert metrics.loc[0, "Warnings"] == "Moderate PDI"


def test_parsed_sample_remains_a_compatible_dls_evidence_alias():
    sample = ParsedSample(
        name="Sample A",
        file_name="sample_a.csv",
        data=None,
        metadata={},
        metrics={},
        warnings=[],
        source_text="",
        measurement=None,
    )

    assert ParsedSample is DLSWorkspaceEvidence
    assert isinstance(sample, DLSSampleEvidence)
