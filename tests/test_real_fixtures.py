"""Regression tests against real (trimmed) Malvern Zetasizer exports.

The fixtures in ``tests/fixtures`` are trimmed copies of genuine Orchestra
Zetasizer exports for project lot 446-01 ("Lot 1"): a dual-angle
summary/statistics workbook, a size-distribution-by-intensity workbook with
multiple replicate column pairs, and a correlogram workbook. They preserve the
real header shapes (e.g. ``Size (d.nm) - ... [Steady state]`` and
``Correlation Coefficient (g₂-1) - ...``) so the importer and metric engine are
exercised against formats the app actually receives, not just synthetic tables.

If these assertions fail after a parser change, confirm against the real export
before relaxing them.
"""

from pathlib import Path

from pytest import approx

from labassistant.importers.file_classifier import (
    CORRELOGRAM,
    INTENSITY_DISTRIBUTION,
    SUMMARY_EXPORT,
)
from labassistant.importers.measurement_importer import (
    build_import_preview,
    import_measurement_groups,
)

FIXTURES = Path(__file__).parent / "fixtures"
SUMMARY = "Orchestra_Zetasizer_Data_Lot_446-01.xlsx"
INTENSITY = "Size Distribution by Intensity Lot 1.xlsx"
CORRELOGRAM_FILE = "Correlogram lot 1.xlsx"


class FixtureUpload:
    """Minimal stand-in for a Streamlit UploadedFile backed by a real file."""

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


def _import_lot_1():
    uploads = [FixtureUpload(SUMMARY), FixtureUpload(INTENSITY), FixtureUpload(CORRELOGRAM_FILE)]
    preview = build_import_preview(uploads)
    results = import_measurement_groups(preview.groups)
    return preview, results


def test_real_exports_classify_and_group_into_one_complete_lot():
    preview, _ = _import_lot_1()

    assert len(preview.groups) == 1
    group = preview.groups[0]
    assert group.lot == "Lot 1"
    assert group.status == "Complete"
    assert group.summary_files[0].file_type == SUMMARY_EXPORT
    assert group.intensity_files[0].file_type == INTENSITY_DISTRIBUTION
    assert group.correlogram_files[0].file_type == CORRELOGRAM


def test_real_summary_metrics_match_the_orchestra_stats_block():
    _, results = _import_lot_1()
    measurement = results[0].measurement

    assert results[0].errors == []
    summary = measurement.summary_metrics
    # Values taken directly from the "Summary" stats block in the export.
    assert summary.z_average == approx(359.14, abs=0.1)
    assert summary.pdi == approx(0.3226, abs=0.001)
    assert summary.max_z_average == approx(499.3, abs=0.1)
    assert summary.measurement_count == 18


def test_real_intensity_distribution_drives_derived_metrics():
    _, results = _import_lot_1()
    derived = results[0].measurement.derived_metrics

    # Single clean intensity peak around 420 nm for replicate 1.
    assert derived.peak_count == 1
    assert derived.primary_peak_nm == approx(420.2, abs=0.1)
    assert derived.d50_nm == approx(420.2, abs=0.1)
    assert derived.peak_width_ratio is not None and derived.peak_width_ratio > 1.0
    assert derived.peak_symmetry is not None
    assert derived.aggregation_risk in {"Low", "Moderate", "High"}
    assert derived.quality_score is not None and 0.0 <= derived.quality_score <= 100.0


def test_real_dual_angle_summary_is_split_forward_and_back():
    _, results = _import_lot_1()
    measurement = results[0].measurement

    # The Orchestra summary is a dual-angle run (forward 12.78° + back 174.7°).
    assert measurement.metadata.measurement_datetime is not None
    by_position = {angle.position: angle for angle in measurement.angle_summaries}
    assert set(by_position) == {"forward", "back"}

    forward = by_position["forward"]
    back = by_position["back"]
    # Matches the "Forward 12.78°" / "Back 174.7°" columns of the stats block.
    assert forward.z_average == approx(453.08, abs=0.5)
    assert back.z_average == approx(265.2, abs=0.5)
    assert forward.count == 9 and back.count == 9
    # Forward scatter reports the larger apparent size.
    assert forward.z_average > back.z_average


def test_real_intensity_replicates_split_by_angle():
    _, results = _import_lot_1()
    measurement = results[0].measurement
    by_position = {angle.position: angle for angle in measurement.angle_summaries}

    # Each angle gets its own representative peak from its classified replicates.
    assert by_position["forward"].primary_peak_nm == approx(420.2, abs=0.1)
    assert by_position["back"].primary_peak_nm == approx(267.2, abs=0.1)
    assert by_position["forward"].primary_peak_nm > by_position["back"].primary_peak_nm
    assert "angle_forward" in measurement.distributions
    assert "angle_back" in measurement.distributions


def test_real_dual_angle_aggregation_index_is_elevated():
    from labassistant.aggregation import assess_dual_angle_aggregation

    _, results = _import_lot_1()
    measurement = results[0].measurement

    # Forward 453 nm / back 265 nm -> index ~0.71, well above the 0.10 elevated line.
    assert measurement.derived_metrics.aggregation_index == approx(0.709, abs=0.02)
    assessment = assess_dual_angle_aggregation(measurement)
    assert assessment.available is True
    assert assessment.elevated is True
    assert assessment.level == "High"
    assert assessment.forward.angle_degrees == approx(12.78, abs=0.1)
    assert assessment.backward.angle_degrees == approx(174.7, abs=0.5)
    assert "Dual-angle aggregation" in [flag.label for flag in measurement.flags]

    # Refined corroboration: a strong-band signal with a real forward peak shift.
    # (The full 9+9-replicate export lands on "corroborated"; the trimmed fixture,
    # with only one backscatter replicate and a shorter correlogram baseline, lands
    # on "repeat recommended" — both are valid Strong-band outcomes.)
    assert assessment.category in ("Strong signal, corroborated", "Strong signal, repeat recommended")
    assert assessment.corroboration_score >= 2
    assert any(check.label == "Forward vs back peak shift" and check.status == "supports" for check in assessment.checks)
    assert "Requires corroboration" in assessment.recommendation


def test_real_correlogram_yields_baseline_noise_across_replicates():
    _, results = _import_lot_1()
    measurement = results[0].measurement

    # The fixture keeps 3 replicate column pairs.
    assert len(measurement.provenance.get("correlogram_replicates", [])) == 3
    noise = measurement.derived_metrics.correlogram_noise_score
    # Baseline scatter should be small and positive, not the whole-curve spread.
    assert noise is not None and 0.0 < noise < 0.1
