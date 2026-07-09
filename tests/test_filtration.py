from io import StringIO

from labassistant.filtration import (
    FILTRATION_DIFFICULTY_RUBRIC,
    filtration_measurement_from_dict,
    normalize_pressure,
    pressure_unit_label,
    validate_difficulty_score,
)
from labassistant.importers.filtration import parse_filtration_csv
from labassistant.models import FiltrationMeasurement, FiltrationTrace


def test_filtration_rubric_and_score_validation_are_ordinal():
    assert FILTRATION_DIFFICULTY_RUBRIC[1].startswith("Filters easily")
    assert validate_difficulty_score("1") == 1
    assert validate_difficulty_score(5.0) == 5
    assert validate_difficulty_score(2.5) is None
    assert validate_difficulty_score(6) is None


def test_pressure_normalization_to_kpa():
    assert normalize_pressure(1000, "Pa") == 1.0
    assert normalize_pressure(2, "bar") == 200.0
    assert round(normalize_pressure(10, "psi"), 3) == 68.948
    assert pressure_unit_label("kpa") == "kPa"


def test_filtration_measurement_round_trips_trace_and_normalized_pressure():
    measurement = FiltrationMeasurement(
        sample_name="Lot 1",
        difficulty_score=4,
        pressure=10,
        pressure_unit="psi",
        pressure_kpa=normalize_pressure(10, "psi"),
        trace=FiltrationTrace(
            time_values=[0, 1, 2],
            time_unit="minutes",
            time_minutes=[0, 1, 2],
            pressure_values=[5, 8, 10],
            pressure_unit="psi",
            pressure_kpa=[normalize_pressure(value, "psi") for value in [5, 8, 10]],
            flow_rate_values=[1.0, 0.8, 0.4],
            flow_rate_unit="mL/min",
        ),
    )

    restored = filtration_measurement_from_dict(measurement.to_dict())

    assert restored.pressure_kpa == measurement.pressure_kpa
    assert restored.trace is not None
    assert restored.trace.pressure_kpa[-1] == measurement.trace.pressure_kpa[-1]


def test_parse_filtration_csv_imports_rows_and_reports_warnings():
    csv = StringIO(
        """sample name,difficulty score,filtration time,filtration time unit,pressure,pressure unit,filter type,clogging observed,notes
Lot 1,2,30,seconds,10,psi,PES,no,ok
Lot 2,5,2,minutes,1,bar,PES,yes,slow
Lot 3,7,1,minutes,100,kPa,PES,no,bad score
"""
    )

    result = parse_filtration_csv(csv, source_name="filtration.csv")

    assert len(result.measurements) == 2
    first = result.measurements[0]
    assert first.sample_name == "Lot 1"
    assert first.difficulty_score == 2.0
    assert first.filtration_time_minutes == 0.5
    assert round(first.pressure_kpa, 3) == 68.948
    assert first.source_file == "filtration.csv"
    assert first.metadata["pressure_unit_original"] == "psi"
    assert any("difficulty score" in warning for warning in result.warnings)


def test_parse_filtration_csv_requires_sample_and_difficulty_columns():
    result = parse_filtration_csv(StringIO("sample,pressure\nLot 1,10\n"), source_name="bad.csv")

    assert result.measurements == []
    assert result.missing_columns == ["difficulty_score"]
    assert result.errors
