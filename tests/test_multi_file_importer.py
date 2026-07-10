from __future__ import annotations

from io import BytesIO

import pandas as pd

from labassistant.importers.file_classifier import (
    CORRELOGRAM,
    INTENSITY_DISTRIBUTION,
    SUMMARY_EXPORT,
    classify_uploaded_file,
)
from labassistant.importers.lot_grouper import detect_lot_key, group_files_by_lot, preview_rows
from labassistant.importers.measurement_importer import (
    _refresh_distribution_metrics_from_intensity,
    build_import_preview,
    import_measurement_groups,
)
from labassistant.models import DerivedMetrics, DistributionData, Measurement, MeasurementMetadata
from app import data_completeness_rows


class FakeUpload:
    def __init__(self, name: str, text: str | bytes):
        self.name = name
        self._content = text if isinstance(text, bytes) else text.encode("utf-8")
        self._position = 0

    def seek(self, position: int) -> None:
        self._position = position

    def read(self) -> bytes:
        content = self._content[self._position :]
        self._position = len(self._content)
        return content


def xlsx_upload(name: str, data: pd.DataFrame) -> FakeUpload:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, header=False)
    return FakeUpload(name, buffer.getvalue())


def test_classifies_uploaded_files_from_name_and_content():
    summary = FakeUpload(
        "Lot 1 summary.csv",
        """Index,Sample Name,Measurement Date/Time,Scattering Collection (°),Z-Average (nm),PDI
1,Lot 1,2026-07-01 10:00,173,125,0.21
2,Lot 1,2026-07-01 10:05,173,127,0.23
""",
    )
    intensity = FakeUpload(
        "Lot 1 intensity distribution.csv",
        """Diameter (nm),Intensity Rep 1 (%),Intensity Rep 2 (%)
50,5,4
100,100,95
200,12,15
""",
    )
    correlogram = FakeUpload(
        "Lot 1 correlogram.csv",
        """Delay Time,Correlation Rep 1,Correlation Rep 2
0.1,0.98,0.97
1.0,0.75,0.74
""",
    )

    assert classify_uploaded_file(summary).file_type == SUMMARY_EXPORT
    assert classify_uploaded_file(intensity).file_type == INTENSITY_DISTRIBUTION
    assert classify_uploaded_file(correlogram).file_type == CORRELOGRAM


def test_groups_by_lot_patterns_and_builds_preview_statuses():
    uploads = [
        FakeUpload("Lot 1 summary.csv", "Z-Average,100\nPDI,0.2\n"),
        FakeUpload("Lot 1 correlogram.csv", "Delay Time,Correlation\n0.1,0.9\n"),
        FakeUpload("446-02 intensity distribution.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
    ]

    groups = group_files_by_lot([classify_uploaded_file(upload) for upload in uploads])
    rows = preview_rows(groups)

    assert [group.lot_key for group in groups] == ["lot_1", "lot_2"]
    assert [group.lot for group in groups] == ["Lot 1", "Lot 2"]
    assert rows[0]["Status"] == "Missing intensity distribution"
    assert rows[1]["Status"] == "Missing summary, Missing correlogram"


def test_normalizes_project_lot_suffixes_to_lot_numbers():
    uploads = [
        FakeUpload("446-01.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
        FakeUpload("Lot 446-01.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
        FakeUpload("Lyo 446-01.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
        FakeUpload("Lot 1.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
        FakeUpload("446-02.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
        FakeUpload("Lot 446-03.csv", "Diameter (nm),Intensity (%)\n100,1\n"),
    ]

    assert [detect_lot_key(classify_uploaded_file(upload)) for upload in uploads] == [
        "lot_1",
        "lot_1",
        "lot_1",
        "lot_1",
        "lot_2",
        "lot_3",
    ]


def test_preview_groups_orchestra_summary_files_with_lot_number_exports():
    uploads = [
        xlsx_upload(
            "Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
            pd.DataFrame(
                [
                    ["Index", "Sample Name", "Measurement Date/Time", "Scattering Collection (°)", "Z-Average (nm)", "PDI"],
                    [1, "Lot 446-01", "2026-07-01 10:00", 173, 125, 0.21],
                ]
            ),
        ),
        xlsx_upload("Size Distribution by Intensity Lot 1.xlsx", pd.DataFrame([["Diameter (nm)", "Intensity Rep 1 (%)"], [50, 5], [100, 100]])),
        xlsx_upload("Correlogram lot 1.xlsx", pd.DataFrame([["Delay Time", "Correlation Rep 1"], [0.1, 0.98], [1.0, 0.75]])),
        xlsx_upload(
            "Orchestra_Zetasizer_Data_Lot_446-02.xlsx",
            pd.DataFrame(
                [
                    ["Index", "Sample Name", "Measurement Date/Time", "Scattering Collection (°)", "Z-Average (nm)", "PDI"],
                    [1, "Lot 446-02", "2026-07-01 10:00", 173, 135, 0.22],
                ]
            ),
        ),
        xlsx_upload("Size Distribution by Intensity Lot 2.xlsx", pd.DataFrame([["Diameter (nm)", "Intensity Rep 1 (%)"], [50, 6], [100, 90]])),
        xlsx_upload("Correlogram lot 2.xlsx", pd.DataFrame([["Delay Time", "Correlation Rep 1"], [0.1, 0.97], [1.0, 0.74]])),
        xlsx_upload(
            "Orchestra_Zetasizer_Data_Lot_446-03.xlsx",
            pd.DataFrame(
                [
                    ["Index", "Sample Name", "Measurement Date/Time", "Scattering Collection (°)", "Z-Average (nm)", "PDI"],
                    [1, "Lot 446-03", "2026-07-01 10:00", 173, 145, 0.23],
                ]
            ),
        ),
        xlsx_upload("Size Distribution by Intensity Lot 3.xlsx", pd.DataFrame([["Diameter (nm)", "Intensity Rep 1 (%)"], [50, 7], [100, 80]])),
        xlsx_upload("Correlogram Lot 3.xlsx", pd.DataFrame([["Delay Time", "Correlation Rep 1"], [0.1, 0.96], [1.0, 0.73]])),
    ]

    preview = build_import_preview(uploads)
    rows = preview.table.to_dict("records")

    assert rows == [
        {
            "Lot": "Lot 1",
            "Summary file": "Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
            "Intensity file": "Size Distribution by Intensity Lot 1.xlsx",
            "Correlogram file": "Correlogram lot 1.xlsx",
            "Status": "Complete",
        },
        {
            "Lot": "Lot 2",
            "Summary file": "Orchestra_Zetasizer_Data_Lot_446-02.xlsx",
            "Intensity file": "Size Distribution by Intensity Lot 2.xlsx",
            "Correlogram file": "Correlogram lot 2.xlsx",
            "Status": "Complete",
        },
        {
            "Lot": "Lot 3",
            "Summary file": "Orchestra_Zetasizer_Data_Lot_446-03.xlsx",
            "Intensity file": "Size Distribution by Intensity Lot 3.xlsx",
            "Correlogram file": "Correlogram Lot 3.xlsx",
            "Status": "Complete",
        },
    ]


def test_data_completeness_rows_show_files_used_by_role():
    uploads = [
        xlsx_upload(
            "Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
            pd.DataFrame(
                [
                    ["Index", "Sample Name", "Measurement Date/Time", "Scattering Collection (°)", "Z-Average (nm)", "PDI"],
                    [1, "Lot 446-01", "2026-07-01 10:00", 173, 125, 0.21],
                ]
            ),
        ),
        xlsx_upload("Size Distribution by Intensity Lot 1.xlsx", pd.DataFrame([["Diameter (nm)", "Intensity Rep 1 (%)"], [50, 5], [100, 100]])),
        xlsx_upload("Correlogram lot 1.xlsx", pd.DataFrame([["Delay Time", "Correlation Rep 1"], [0.1, 0.98], [1.0, 0.75]])),
    ]

    preview = build_import_preview(uploads)

    assert data_completeness_rows(preview.groups) == [
        {
            "Lot": "Lot 1",
            "Summary": "✓ Orchestra_Zetasizer_Data_Lot_446-01.xlsx",
            "Intensity distribution": "✓ Size Distribution by Intensity Lot 1.xlsx",
            "Correlogram": "✓ Correlogram lot 1.xlsx",
            "Status": "Complete",
        }
    ]


def test_imports_grouped_measurement_from_summary_intensity_and_correlogram():
    uploads = [
        FakeUpload(
            "Lot 1 summary.csv",
            """Index,Sample Name,Measurement Date/Time,Scattering Collection (°),Z-Average (nm),PDI
1,Lot 1,2026-07-01 10:00,173,125,0.21
2,Lot 1,2026-07-01 10:05,173,127,0.23
""",
        ),
        FakeUpload(
            "Lot 1 intensity distribution.csv",
            """Diameter (nm),Intensity Rep 1 (%),Intensity Rep 2 (%)
50,5,4
100,100,95
200,12,15
""",
        ),
        FakeUpload(
            "Lot 1 correlogram.csv",
            """Delay Time,Correlation Rep 1,Correlation Rep 2
0.1,0.98,0.97
1.0,0.75,0.74
""",
        ),
    ]

    preview = build_import_preview(uploads)
    results = import_measurement_groups(preview.groups)
    measurement = results[0].measurement

    assert preview.table.to_dict("records")[0]["Status"] == "Complete"
    assert results[0].errors == []
    assert measurement is not None
    assert measurement.sample_name == "Lot 1"
    assert measurement.summary_metrics.z_average == 126.0
    assert measurement.summary_metrics.pdi == 0.22
    assert measurement.distributions["intensity_replicate_1"].intensity == [5.0, 100.0, 12.0]
    assert measurement.distributions["intensity_replicate_2"].intensity == [4.0, 95.0, 15.0]
    assert measurement.derived_metrics.primary_peak_nm == 100.0
    assert measurement.derived_metrics.d50_nm == 100.0
    assert measurement.derived_metrics.correlogram_noise_score is not None
    assert measurement.provenance["derived_metrics_source"] == "mean intensity distribution (2 replicates)"
    assert measurement.provenance["correlogram_quality_source"] == "correlogram"
    assert len(measurement.correlogram) == 4
    assert set(measurement.metadata.source_files) == {
        "Lot 1 summary.csv",
        "Lot 1 intensity distribution.csv",
        "Lot 1 correlogram.csv",
    }
    assert pd.DataFrame(preview.table).columns.tolist() == [
        "Lot",
        "Summary file",
        "Intensity file",
        "Correlogram file",
        "Status",
    ]


def test_lot_metrics_average_single_angle_replicates_instead_of_using_replicate_one():
    uploads = [
        FakeUpload(
            "Lot 1 summary.csv",
            """Index,Sample Name,Scattering Collection (°),Z-Average (nm),PDI
1,Lot 1,173,100,0.2
""",
        ),
        FakeUpload(
            "Lot 1 intensity distribution.csv",
            """Diameter (nm),Intensity Rep 1 (%),Intensity Rep 2 (%)
50,100,0
100,0,100
200,0,0
""",
        ),
    ]

    measurement = import_measurement_groups(build_import_preview(uploads).groups)[0].measurement

    assert measurement is not None
    assert measurement.derived_metrics.primary_peak_nm == 50.0
    assert measurement.derived_metrics.d50_nm == 50.0
    assert measurement.provenance["derived_metrics_source"] == "mean intensity distribution (2 replicates)"


def test_lot_metrics_do_not_substitute_volume_when_intensity_is_missing():
    measurement = Measurement(
        metadata=MeasurementMetadata(sample_name="Lot 1"),
        distributions={
            "particle_size": DistributionData(
                diameter_nm=[50.0, 100.0, 200.0],
                volume=[5.0, 100.0, 5.0],
            )
        },
        derived_metrics=DerivedMetrics(primary_peak_nm=125.0),
    )

    _refresh_distribution_metrics_from_intensity(measurement)

    assert measurement.derived_metrics.primary_peak_nm == 125.0
    assert "derived_metrics_source" not in measurement.provenance
