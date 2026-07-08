from pathlib import Path

from pytest import approx

from labassistant.chromatography import mass_balance_hypotheses
from labassistant.importers.chromatography import (
    assess_chromatography_mass_balance,
    chromatography_observations,
    parse_chromatography_csv,
    peak_area_trend_table,
    total_area_trend_table,
)


FIXTURE = Path("sample_data/chromatography/mass_balance_demo.csv")


def test_parse_chromatography_fixture_into_measurements_and_peaks():
    measurements = parse_chromatography_csv(FIXTURE)

    assert len(measurements) == 6
    first = measurements[0]
    assert first.sample_name == "Formulation A"
    assert first.timepoint == "T0"
    assert first.injection_id == "Formulation A-T0-inj1"
    assert first.total_area == approx(1040.0)
    assert [peak.role for peak in first.peaks] == ["parent", "known_impurity", "unknown"]
    assert first.peaks[0].area_percent == approx(96.1538, abs=0.001)


def test_chromatography_fixture_generates_mass_balance_observations():
    measurements = parse_chromatography_csv(FIXTURE)
    assessment = assess_chromatography_mass_balance(measurements)
    observations = chromatography_observations(measurements, assessment)
    labels = [observation.label for observation in observations]

    assert assessment.parent_change_percent == approx(-41.206, abs=0.001)
    assert assessment.total_area_change_percent == approx(-24.710, abs=0.001)
    assert assessment.unknown_area_percent == approx(7.3718, abs=0.001)
    assert assessment.retention_time_shift_min == approx(0.335, abs=0.001)
    assert assessment.replicate_rsd_percent == approx(16.318, abs=0.001)
    assert len(observations) >= 3
    assert "Parent peak decreased" in labels
    assert "Unknown peak appeared" in labels
    assert "Total area decreased" in labels
    assert "Retention time shifted" in labels
    assert "Replicate %RSD elevated" in labels


def test_chromatography_fixture_tables_and_hypotheses_are_available():
    measurements = parse_chromatography_csv(FIXTURE)
    assessment = assess_chromatography_mass_balance(measurements)
    observations = chromatography_observations(measurements, assessment)
    peak_trend = peak_area_trend_table(measurements)
    total_trend = total_area_trend_table(measurements)
    hypotheses = mass_balance_hypotheses(observations)

    assert peak_trend["Timepoint"].tolist() == ["T0", "T1", "T2"]
    assert total_trend["Change vs Start %"].iloc[-1] == approx(-24.710, abs=0.001)
    assert "Degradation into detected impurities" in hypotheses
    assert "Method instability or integration error" in hypotheses
