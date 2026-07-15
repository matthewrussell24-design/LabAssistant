from __future__ import annotations

import math

import pandas as pd


def _distribution_profile(
    data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None
) -> tuple[list[float], list[float]] | None:
    """Return cleaned, size-sorted (diameter, weight) points or ``None``.

    Shared helper for the shape metrics. Drops missing rows, negative weights,
    and non-positive diameters (diameters must be positive to work in log space).
    """
    if not diameter_column or not distribution_column:
        return None

    working = data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    if len(working) < 3:
        return None

    x_values = [float(value) for value in working[diameter_column].to_list()]
    y_values = [float(value) for value in working[distribution_column].to_list()]

    if max(y_values) <= 0:
        return None

    return x_values, y_values


def find_local_peaks(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> list[dict[str, float]]:
    if not diameter_column or not distribution_column:
        return []

    working = data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    if len(working) < 3:
        return []

    return find_local_peaks_from_values(
        working[diameter_column].to_list(),
        working[distribution_column].to_list(),
    )


def find_local_peaks_from_values(
    x_values: list[float], y_values: list[float]
) -> list[dict[str, float]]:
    """Find peaks in cleaned, diameter-sorted distribution values."""

    if len(x_values) < 3 or len(y_values) < 3:
        return []

    max_y = max(y_values)

    if max_y <= 0:
        return []

    peaks = []
    if y_values[0] >= y_values[1] and y_values[0] >= max_y * 0.08:
        peaks.append({"diameter": float(x_values[0]), "value": float(y_values[0])})
    for index in range(1, len(y_values) - 1):
        y = y_values[index]
        if y >= y_values[index - 1] and y >= y_values[index + 1] and y >= max_y * 0.08:
            peaks.append({"diameter": float(x_values[index]), "value": float(y)})
    if y_values[-1] >= y_values[-2] and y_values[-1] >= max_y * 0.08:
        peaks.append({"diameter": float(x_values[-1]), "value": float(y_values[-1])})

    peaks.sort(key=lambda peak: peak["value"], reverse=True)
    deduped = []
    for peak in peaks:
        if all(abs(math.log10(peak["diameter"]) - math.log10(existing["diameter"])) > 0.08 for existing in deduped):
            deduped.append(peak)

    return deduped[:4]


def calculate_tail_index(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None, threshold: float = 1000) -> float | None:
    if not diameter_column or not distribution_column:
        return None

    working = data[[diameter_column, distribution_column]].dropna()
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    total = working[distribution_column].sum()
    if total <= 0:
        return None

    tail = working.loc[working[diameter_column] >= threshold, distribution_column].sum()
    return float(tail / total * 100)


def calculate_width_ratio(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> float | None:
    if not diameter_column or not distribution_column:
        return None

    working = data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    if working.empty or working[distribution_column].sum() <= 0:
        return None

    weights = working[distribution_column] / working[distribution_column].sum()
    cumulative = weights.cumsum()
    d10 = working.loc[cumulative >= 0.10, diameter_column].iloc[0]
    d90 = working.loc[cumulative >= 0.90, diameter_column].iloc[0]

    if d10 <= 0:
        return None

    return float(d90 / d10)


def calculate_distribution_percentiles(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> dict[str, float | None]:
    percentiles = {"D10": None, "D50": None, "D90": None}

    if not diameter_column or not distribution_column:
        return percentiles

    working = data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    if working.empty or working[distribution_column].sum() <= 0:
        return percentiles

    weights = working[distribution_column] / working[distribution_column].sum()
    cumulative = weights.cumsum()

    for label, cutoff in [("D10", 0.10), ("D50", 0.50), ("D90", 0.90)]:
        percentiles[label] = float(working.loc[cumulative >= cutoff, diameter_column].iloc[0])

    return percentiles


def count_peaks(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> int | None:
    """Number of resolved modes in the distribution.

    Returns ``None`` when there is not enough signal to evaluate peaks, so the
    caller can distinguish "no distribution" from "single clean peak".
    """
    if _distribution_profile(data, diameter_column, distribution_column) is None:
        return None
    return len(find_local_peaks(data, diameter_column, distribution_column))


def _half_max_crossing(x_values: list[float], y_values: list[float], peak_index: int, half: float, step: int) -> float | None:
    """Interpolate, in log10(diameter) space, where the curve falls to ``half``.

    Walks outward from the peak in the given direction (``step`` = -1 left, +1
    right). Returns the crossing diameter in nm, or ``None`` if the curve never
    reaches half height on that side (a peak truncated at the data edge).
    """
    index = peak_index
    while 0 <= index + step < len(y_values):
        y_high = y_values[index]
        y_low = y_values[index + step]
        if y_low <= half <= y_high:
            if y_high == y_low:
                return x_values[index + step]
            fraction = (y_high - half) / (y_high - y_low)
            log_low = math.log10(x_values[index])
            log_high = math.log10(x_values[index + step])
            return float(10 ** (log_low + fraction * (log_high - log_low)))
        index += step
    return None


def calculate_peak_width(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> float | None:
    """Full width at half maximum of the primary (tallest) peak.

    Reported as a geometric span ratio (upper diameter / lower diameter) because
    DLS size distributions are approximately log-normal, so a ratio is more
    meaningful than a difference in nm. A value near 1 is a very narrow peak;
    larger values indicate a broader primary population. Returns ``None`` when
    the peak is truncated at a distribution edge (width cannot be trusted).
    """
    profile = _distribution_profile(data, diameter_column, distribution_column)
    if profile is None:
        return None

    x_values, y_values = profile
    peak_index = max(range(len(y_values)), key=lambda i: y_values[i])
    half = y_values[peak_index] / 2.0
    if half <= 0:
        return None

    lower = _half_max_crossing(x_values, y_values, peak_index, half, step=-1)
    upper = _half_max_crossing(x_values, y_values, peak_index, half, step=1)
    if lower is None or upper is None or lower <= 0:
        return None

    return float(upper / lower)


def calculate_peak_symmetry(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> float | None:
    """Symmetry of the primary peak in log-size space.

    Ratio of the right (large-particle) half-width to the left half-width, both
    measured at half maximum in log10(diameter). ``1.0`` is symmetric; values
    ``> 1`` mean the peak tails toward larger sizes (an early aggregation cue);
    values ``< 1`` tail toward smaller sizes. Returns ``None`` when either side
    of the peak is truncated at the data edge.
    """
    profile = _distribution_profile(data, diameter_column, distribution_column)
    if profile is None:
        return None

    x_values, y_values = profile
    peak_index = max(range(len(y_values)), key=lambda i: y_values[i])
    half = y_values[peak_index] / 2.0
    if half <= 0:
        return None

    lower = _half_max_crossing(x_values, y_values, peak_index, half, step=-1)
    upper = _half_max_crossing(x_values, y_values, peak_index, half, step=1)
    if lower is None or upper is None:
        return None

    peak_diameter = x_values[peak_index]
    left_width = math.log10(peak_diameter) - math.log10(lower)
    right_width = math.log10(upper) - math.log10(peak_diameter)
    if left_width <= 0:
        return None

    return float(right_width / left_width)


def calculate_log_skewness(data: pd.DataFrame, diameter_column: str | None, distribution_column: str | None) -> float | None:
    """Intensity-weighted skewness of the size distribution in log space.

    Computed as the third standardized moment of log10(diameter) weighted by the
    distribution. DLS distributions are naturally log-normal, so a symmetric
    log-normal peak scores near 0. Positive values indicate a tail toward larger
    particles (possible aggregates); negative values a tail toward smaller sizes.
    Returns ``None`` when the distribution has no spread.
    """
    profile = _distribution_profile(data, diameter_column, distribution_column)
    if profile is None:
        return None

    x_values, weights = profile
    max_weight = max(weights)
    resolved_points = [(x_value, weight) for x_value, weight in zip(x_values, weights) if weight >= max_weight * 0.20]
    if len(resolved_points) >= 3:
        x_values = [x_value for x_value, _ in resolved_points]
        weights = [weight for _, weight in resolved_points]

    total_weight = sum(weights)
    if total_weight <= 0:
        return None

    log_sizes = [math.log10(value) for value in x_values]
    mean = sum(weight * log_size for weight, log_size in zip(weights, log_sizes)) / total_weight
    variance = sum(weight * (log_size - mean) ** 2 for weight, log_size in zip(weights, log_sizes)) / total_weight
    if variance <= 0:
        return None

    std = math.sqrt(variance)
    third_moment = sum(weight * (log_size - mean) ** 3 for weight, log_size in zip(weights, log_sizes)) / total_weight
    return float(third_moment / std ** 3)


def assess_aggregation_risk(
    *,
    tail_index: float | None = None,
    secondary_peak_nm: float | None = None,
    primary_peak_nm: float | None = None,
    pdi: float | None = None,
    log_skewness: float | None = None,
    width_ratio: float | None = None,
) -> str | None:
    """Classify aggregation/large-particle risk as Low, Moderate, or High.

    Combines several independent cues rather than a single threshold:
    large-particle tail area, a secondary peak that is much larger than the
    primary population, an absolute large secondary peak, elevated PDI, a strong
    positive log-skew, and a very broad distribution. Returns ``None`` when there
    is no evidence at all to judge (no distribution and no PDI).
    """
    inputs = [tail_index, secondary_peak_nm, pdi, log_skewness, width_ratio]
    if all(value is None for value in inputs):
        return None

    score = 0

    if tail_index is not None:
        if tail_index >= 10:
            score += 3
        elif tail_index >= 5:
            score += 2
        elif tail_index >= 2:
            score += 1

    if secondary_peak_nm is not None and primary_peak_nm and primary_peak_nm > 0:
        peak_ratio = secondary_peak_nm / primary_peak_nm
        if peak_ratio >= 3:
            score += 2
        elif peak_ratio >= 1.5:
            score += 1
    if secondary_peak_nm is not None and secondary_peak_nm >= 1000:
        score += 1

    if pdi is not None:
        if pdi >= 0.7:
            score += 2
        elif pdi >= 0.5:
            score += 1

    if log_skewness is not None and log_skewness >= 1.0:
        score += 1

    if width_ratio is not None and width_ratio >= 10:
        score += 1

    if score >= 4:
        return "High"
    if score >= 2:
        return "Moderate"
    return "Low"


def calculate_quality_score(
    *,
    pdi: float | None = None,
    tail_index: float | None = None,
    width_ratio: float | None = None,
    secondary_peak_nm: float | None = None,
    correlogram_noise: float | None = None,
) -> float | None:
    """Heuristic 0-100 screening score for how clean a measurement looks.

    Starts at 100 and subtracts capped penalties for high PDI, a large-particle
    tail, an unusually broad distribution, the presence of a secondary peak, and
    correlogram baseline noise when available. This is a screening aid to rank
    samples, not an absolute quality certificate. Returns ``None`` when there is
    nothing to score.
    """
    if all(value is None for value in [pdi, tail_index, width_ratio, secondary_peak_nm, correlogram_noise]):
        return None

    score = 100.0

    if pdi is not None:
        score -= min(max(pdi, 0.0) * 80.0, 45.0)
    if tail_index is not None:
        score -= min(max(tail_index, 0.0) * 2.0, 25.0)
    if width_ratio is not None and width_ratio > 3:
        score -= min((width_ratio - 3) * 2.0, 15.0)
    if secondary_peak_nm is not None:
        score -= 10.0
    if correlogram_noise is not None:
        score -= min(max(correlogram_noise, 0.0) * 100.0, 15.0)

    return round(max(score, 0.0), 1)
