import math

import pandas as pd
from pytest import approx

from labassistant.metrics import (
    assess_aggregation_risk,
    calculate_distribution_percentiles,
    calculate_log_skewness,
    calculate_peak_symmetry,
    calculate_peak_width,
    calculate_quality_score,
    calculate_tail_index,
    calculate_width_ratio,
    count_peaks,
    find_local_peaks,
)


def _symmetric_log_peak() -> pd.DataFrame:
    """Gaussian in log10(diameter): symmetric peak centered at 100 nm (log10 = 2)."""
    diameters = [10 ** (2.0 + 0.1 * step) for step in range(-15, 16)]
    intensities = [100 * math.exp(-((math.log10(d) - 2.0) ** 2) / (2 * 0.3 ** 2)) for d in diameters]
    return pd.DataFrame({"Diameter": diameters, "Intensity": intensities})


def test_distribution_percentiles_use_signal_weighted_cumulative_curve():
    data = pd.DataFrame({"Diameter": [10, 20, 30, 40], "Intensity": [1, 1, 6, 2]})

    assert calculate_distribution_percentiles(data, "Diameter", "Intensity") == {
        "D10": 10.0,
        "D50": 30.0,
        "D90": 40.0,
    }


def test_tail_index_returns_percent_above_threshold():
    data = pd.DataFrame({"Diameter": [100, 500, 1000, 2000], "Intensity": [40, 40, 10, 10]})

    assert calculate_tail_index(data, "Diameter", "Intensity", threshold=1000) == 20.0


def test_width_ratio_uses_d90_over_d10():
    data = pd.DataFrame({"Diameter": [10, 20, 40, 80], "Intensity": [1, 1, 6, 2]})

    assert calculate_width_ratio(data, "Diameter", "Intensity") == 8.0


def test_peak_detection_sorts_by_signal_and_dedupes_nearby_peaks():
    data = pd.DataFrame(
        {
            "Diameter": [50, 100, 110, 220, 500, 1000],
            "Intensity": [1, 100, 95, 5, 30, 1],
        }
    )

    peaks = find_local_peaks(data, "Diameter", "Intensity")

    assert peaks == [
        {"diameter": 100.0, "value": 100.0},
        {"diameter": 500.0, "value": 30.0},
    ]


def test_metric_functions_return_empty_values_for_missing_or_invalid_data():
    data = pd.DataFrame({"Diameter": [10, 20], "Intensity": [0, 0]})

    assert find_local_peaks(data, None, "Intensity") == []
    assert calculate_tail_index(data, "Diameter", "Intensity") is None
    assert calculate_width_ratio(data, "Diameter", "Intensity") is None
    assert calculate_distribution_percentiles(data, "Diameter", "Intensity") == {
        "D10": None,
        "D50": None,
        "D90": None,
    }


def test_count_peaks_counts_resolved_modes():
    # find_local_peaks only reports interior maxima, so both modes sit off the edges.
    single = pd.DataFrame({"Diameter": [50, 100, 200, 400, 800], "Intensity": [1, 20, 100, 20, 1]})
    bimodal = pd.DataFrame(
        {"Diameter": [50, 100, 200, 400, 800, 1600], "Intensity": [1, 100, 10, 10, 90, 1]}
    )

    assert count_peaks(single, "Diameter", "Intensity") == 1
    assert count_peaks(bimodal, "Diameter", "Intensity") == 2
    assert count_peaks(single, None, "Intensity") is None


def test_peak_width_is_symmetric_for_log_gaussian():
    data = _symmetric_log_peak()

    width = calculate_peak_width(data, "Diameter", "Intensity")
    symmetry = calculate_peak_symmetry(data, "Diameter", "Intensity")

    # A log-Gaussian FWHM spans about 2.355 * sigma in log10 -> ratio ~ 10 ** (2.355*0.3).
    assert width == approx(10 ** (2.3548 * 0.3), rel=0.05)
    assert symmetry == approx(1.0, abs=0.05)


def test_peak_width_and_symmetry_return_none_when_peak_truncated():
    # Monotonic rise: the peak sits at the right edge, so half-max is not bracketed.
    data = pd.DataFrame({"Diameter": [100, 200, 300], "Intensity": [1, 5, 9]})

    assert calculate_peak_width(data, "Diameter", "Intensity") is None
    assert calculate_peak_symmetry(data, "Diameter", "Intensity") is None


def test_log_skewness_sign_tracks_the_heavy_tail():
    symmetric = _symmetric_log_peak()
    right_tailed = pd.DataFrame({"Diameter": [100, 200, 400, 2000], "Intensity": [100, 60, 20, 15]})
    left_tailed = pd.DataFrame({"Diameter": [10, 50, 200, 400], "Intensity": [15, 20, 60, 100]})

    assert calculate_log_skewness(symmetric, "Diameter", "Intensity") == approx(0.0, abs=0.05)
    assert calculate_log_skewness(right_tailed, "Diameter", "Intensity") > 0.2
    assert calculate_log_skewness(left_tailed, "Diameter", "Intensity") < -0.2


def test_aggregation_risk_escalates_with_evidence():
    assert assess_aggregation_risk() is None
    assert assess_aggregation_risk(tail_index=0.0, pdi=0.2, width_ratio=2.0) == "Low"
    assert assess_aggregation_risk(tail_index=6.0, pdi=0.4) == "Moderate"
    assert (
        assess_aggregation_risk(
            tail_index=12.0,
            secondary_peak_nm=1500,
            primary_peak_nm=200,
            pdi=0.8,
        )
        == "High"
    )


def test_quality_score_penalizes_dirty_measurements():
    clean = calculate_quality_score(pdi=0.05, tail_index=0.0, width_ratio=1.5)
    dirty = calculate_quality_score(pdi=0.6, tail_index=15.0, width_ratio=12.0, secondary_peak_nm=1200)

    assert clean is not None and dirty is not None
    assert clean > 90
    assert dirty < clean
    assert 0.0 <= dirty <= 100.0
    assert calculate_quality_score() is None
