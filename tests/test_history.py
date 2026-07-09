from __future__ import annotations

from labassistant.history import (
    compare_experiments,
    compare_to_history,
    find_similar_samples,
    history_table,
    latest_experiment,
    load_history,
    save_experiment,
    trend_table,
)
from labassistant.models import DerivedMetrics, Measurement, MeasurementFlag, MeasurementMetadata, SummaryMetrics


def make_measurement(name: str, z_average: float, pdi: float, flags=None, primary_peak: float | None = None) -> Measurement:
    return Measurement(
        metadata=MeasurementMetadata(sample_name=name, source_files=[f"{name}.csv"]),
        summary_metrics=SummaryMetrics(z_average=z_average, pdi=pdi),
        derived_metrics=DerivedMetrics(primary_peak_nm=primary_peak),
        flags=flags or [],
    )


def test_save_and_load_experiment_history(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    measurement = make_measurement("Lot 1", 125.0, 0.21)
    measurement.provenance["total_circulation_time"] = {
        "value": 2.0,
        "unit": "hours",
        "minutes": 120.0,
        "source": "manual_entry",
    }
    measurement.provenance["filtration_follow_up"] = {
        "sample_name": "Lot 1",
        "difficulty_score": 4.0,
        "source": "manual_entry",
    }

    saved = save_experiment([measurement], label="Run A", history_path=history_path)
    records = load_history(history_path)

    assert len(records) == 1
    assert records[0].id == saved.id
    assert records[0].label == "Run A"
    assert records[0].measurements[0]["metadata"]["sample_name"] == "Lot 1"
    assert records[0].measurements[0]["provenance"]["total_circulation_time"]["minutes"] == 120.0
    assert records[0].measurements[0]["provenance"]["filtration_follow_up"]["difficulty_score"] == 4.0


def test_history_and_trend_tables_summarize_records(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    save_experiment(
        [
            make_measurement("Lot 1", 100.0, 0.20),
            make_measurement("Lot 2", 140.0, 0.45, [MeasurementFlag(label="Moderate PDI")]),
        ],
        label="Run A",
        history_path=history_path,
    )

    records = load_history(history_path)
    summary = history_table(records)
    trends = trend_table(records)

    assert summary.loc[0, "Experiment"] == "Run A"
    assert summary.loc[0, "Measurements"] == 2
    assert summary.loc[0, "Flagged"] == 1
    assert summary.loc[0, "Median Z-Average"] == 120.0
    assert trends["Sample"].tolist() == ["Lot 1", "Lot 2"]
    assert trends["Status"].tolist() == ["Normal", "Watch"]


def test_compare_experiments_flags_drift_and_new_samples(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    save_experiment(
        [make_measurement("Lot 1", 100.0, 0.20), make_measurement("Lot 2", 200.0, 0.25)],
        label="Baseline",
        history_path=history_path,
    )
    previous = latest_experiment(load_history(history_path))

    current = [
        make_measurement("Lot 1", 101.0, 0.205),  # stable
        make_measurement("Lot 2", 260.0, 0.25),   # +30% Z -> drift
        make_measurement("Lot 3", 150.0, 0.30),   # new sample
    ]
    comparison = compare_experiments(current, previous)
    drift_by_sample = dict(zip(comparison["Sample"], comparison["Drift"]))

    assert drift_by_sample["Lot 1"] == "Stable"
    assert drift_by_sample["Lot 2"] == "Z-average drift"
    assert drift_by_sample["Lot 3"] == "New sample"
    assert comparison.loc[comparison["Sample"] == "Lot 2", "Z Change %"].iloc[0] == 30.0


def test_compare_experiments_flags_pdi_drift():
    previous = None
    stable = compare_experiments([make_measurement("Lot 1", 100.0, 0.20)], previous)
    assert stable.loc[0, "Drift"] == "New sample"


def test_compare_to_history_uses_latest_saved_run(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    save_experiment([make_measurement("Lot 1", 100.0, 0.20)], label="Older", history_path=history_path)
    save_experiment([make_measurement("Lot 1", 100.0, 0.50)], label="Newer", history_path=history_path)

    comparison = compare_to_history([make_measurement("Lot 1", 100.0, 0.20)], history_path=history_path)

    # Latest saved PDI was 0.50; current 0.20 -> -0.30 absolute change -> PDI drift.
    assert comparison.loc[0, "Drift"] == "PDI drift"
    assert comparison.loc[0, "Previous PDI"] == 0.50


def test_find_similar_samples_ranks_nearest_first(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    save_experiment(
        [
            make_measurement("Small", 100.0, 0.20, primary_peak=95.0),
            make_measurement("Large", 450.0, 0.30, primary_peak=420.0),
            make_measurement("Medium", 120.0, 0.22, primary_peak=110.0),
        ],
        label="Baseline",
        history_path=history_path,
    )
    records = load_history(history_path)

    query = make_measurement("Query", 105.0, 0.21, primary_peak=100.0)
    result = find_similar_samples(query, records, top_n=3)

    assert list(result["Sample"]) == ["Small", "Medium", "Large"]
    assert result.loc[0, "Distance"] <= result.loc[1, "Distance"] <= result.loc[2, "Distance"]
    assert 0.0 <= result.loc[2, "Similarity"] <= result.loc[0, "Similarity"] <= 100.0


def test_find_similar_samples_can_exclude_a_record_and_handles_empty(tmp_path):
    history_path = tmp_path / "experiments.jsonl"
    saved = save_experiment([make_measurement("Lot 1", 100.0, 0.20, primary_peak=95.0)], label="Only", history_path=history_path)
    records = load_history(history_path)

    query = make_measurement("Query", 100.0, 0.20, primary_peak=95.0)
    assert find_similar_samples(query, records, exclude_id=saved.id).empty
    assert not find_similar_samples(query, records).empty
