import pandas as pd

from labassistant.importers.dls import (
    choose_distribution_section,
    extract_metadata,
    find_table_sections,
    format_measurement_date,
    infer_diameter_column,
    infer_distribution_column,
    is_summary_stats_table,
    parse_dls_upload,
    section_to_dataframe,
    summarize_by_angle,
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


def test_find_table_sections_detects_distribution_table_after_metadata():
    text = """Sample Name,Test A
Operator,MT

Diameter (nm),Intensity (%),Volume (%)
10,1,0.5
20,5,2.5
30,1,0.5
"""

    sections = find_table_sections(text)
    data = choose_distribution_section(sections)

    assert extract_metadata(text) == {"Sample Name": "Test A", "Operator": "MT"}
    assert infer_diameter_column(data) == "Diameter (nm)"
    assert infer_distribution_column(data, "Intensity") == "Intensity (%)"
    assert data["Intensity (%)"].tolist() == [1, 5, 1]


def test_section_to_dataframe_handles_zetasizer_measurement_rows_without_header():
    section = {
        "column_count": 6,
        "rows": [
            ["1", "Sample A", "2026-07-01 10:00", "173", "125.5", "0.22"],
            ["2", "Sample A", "2026-07-01 10:05", "173", "126.5", "0.24"],
        ],
    }

    data = section_to_dataframe(section)

    assert data.columns.tolist() == [
        "Index",
        "Sample Name",
        "Measurement Date/Time",
        "Scattering Collection (°)",
        "Z-Average (nm)",
        "PDI",
    ]
    assert data["Z-Average (nm)"].tolist() == [125.5, 126.5]


def test_summary_stats_table_detection_and_excel_date_formatting():
    data = pd.DataFrame({"Name": ["Z-Average", "PDI"], "Mean": [125.0, 0.22]})

    assert is_summary_stats_table(data)
    assert format_measurement_date(45100) == "2023-06-23 00:00:00"


def test_parse_dls_upload_returns_structured_result_from_csv_upload():
    upload = FakeUpload(
        "sample_a.csv",
        """Sample Name,Sample A
Operator,MT
Z-Average,100
PDI,0.31

Diameter (nm),Intensity (%)
50,5
100,100
200,10
""",
    )

    result = parse_dls_upload(upload)

    assert result.name == "Sample A"
    assert result.file_name == "sample_a.csv"
    assert result.metadata["Operator"] == "MT"
    assert result.metrics["Data Type"] == "Distribution Curve"
    assert result.metrics["Primary Peak"] == 100.0
    assert result.metrics["D50"] == 100.0
    assert result.warnings == ["Moderate PDI"]


def test_summarize_by_angle_groups_interleaved_measurements():
    data = pd.DataFrame(
        {
            "Scattering Collection (°)": [12.78, 174.7, 12.78, 174.7, 174.7],
            "Z-Average (nm)": [450.0, 260.0, 460.0, 270.0, 280.0],
            "PDI": [0.30, 0.34, 0.32, 0.35, 0.36],
        }
    )

    summaries = summarize_by_angle(data, "Scattering Collection (°)", "Z-Average (nm)", "PDI")

    by_angle = {summary["angle_degrees"]: summary for summary in summaries}
    assert set(by_angle) == {12.78, 174.7}
    assert by_angle[12.78]["position"] == "forward"
    assert by_angle[12.78]["count"] == 2
    assert by_angle[12.78]["z_average"] == 455.0
    assert by_angle[174.7]["position"] == "back"
    assert by_angle[174.7]["count"] == 3
    assert by_angle[174.7]["max_z_average"] == 280.0


def test_summarize_by_angle_needs_two_angles():
    data = pd.DataFrame({"Scattering Collection (°)": [173.0, 173.0], "Z-Average (nm)": [260.0, 265.0], "PDI": [0.3, 0.3]})

    assert summarize_by_angle(data, "Scattering Collection (°)", "Z-Average (nm)", "PDI") == []
