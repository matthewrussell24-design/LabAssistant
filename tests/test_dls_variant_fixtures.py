"""Synthetic, non-sensitive regression fixtures for DLS export variations."""

from pathlib import Path

from labassistant.importers.dls import parse_dls_upload
from labassistant.importers.file_classifier import INTENSITY_DISTRIBUTION, SUMMARY_EXPORT, UNKNOWN, classify_uploaded_file


FIXTURES = Path(__file__).parent / "fixtures" / "dls_variants"


class FixtureUpload:
    def __init__(self, name: str):
        self.name = name
        self._content = (FIXTURES / name).read_bytes()
        self._position = 0

    def seek(self, position: int) -> None:
        self._position = position

    def read(self) -> bytes:
        content = self._content[self._position :]
        self._position = len(self._content)
        return content


def test_semicolon_decimal_comma_distribution_parses_numeric_values():
    upload = FixtureUpload("semicolon_decimal_comma.csv")

    result = parse_dls_upload(upload)
    classified = classify_uploaded_file(upload)

    assert result.data["Diameter (nm)"].tolist() == [50.0, 100.0, 200.0]
    assert result.metrics["Z-Average"] == 125.5
    assert result.metrics["PDI"] == 0.21
    assert result.metrics["Primary Peak"] == 100.0
    assert result.metrics["D50"] == 100.0
    assert classified.file_type == INTENSITY_DISTRIBUTION


def test_single_angle_summary_preserves_one_angle_summary():
    upload = FixtureUpload("single_angle_summary.csv")

    result = parse_dls_upload(upload)
    classified = classify_uploaded_file(upload)

    assert classified.file_type == SUMMARY_EXPORT
    assert result.metrics["Scattering Angles"] == "173°"
    assert result.angle_summaries == [
        {
            "angle_degrees": 173.0,
            "position": "back",
            "count": 2,
            "z_average": 126.0,
            "pdi": 0.22,
            "max_z_average": 127.0,
        }
    ]


def test_volume_and_number_only_distributions_are_rejected_as_intensity_roles():
    for name, column in [
        ("volume_only_distribution.csv", "Volume Column"),
        ("number_only_distribution.csv", "Number Column"),
    ]:
        upload = FixtureUpload(name)
        result = parse_dls_upload(upload)
        classified = classify_uploaded_file(upload)

        assert result.metrics[column] is not None
        assert result.metrics["Intensity Column"] is None
        assert result.metrics["Primary Peak"] is None
        assert result.metrics["D50"] is None
        assert classified.file_type == UNKNOWN
        assert classified.error == "An intensity distribution is required for DLS derived metrics."
