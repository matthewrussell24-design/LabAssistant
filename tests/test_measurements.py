import pandas as pd

from labassistant.importers.dls import ParsedDLSResult
from labassistant.measurements import measurement_from_dls_result


def test_measurement_from_dls_result_maps_importer_shape():
    result = ParsedDLSResult(
        name="Batch A",
        file_name="batch_a.csv",
        data=pd.DataFrame(
            {
                "Diameter (nm)": [50, 100, 200],
                "Intensity (%)": [5, 100, 10],
                "Volume (%)": [3, 80, 8],
            }
        ),
        metadata={"Operator": "MT", "Temperature": "25 C"},
        metrics={
            "Data Type": "Distribution Curve",
            "Z-Average": 105.5,
            "PDI": 0.31,
            "Max Z-Average": None,
            "Max PDI": None,
            "Measurement Count": None,
            "Scattering Angles": None,
            "Primary Peak": 100.0,
            "Secondary Peak": None,
            "Count Rate": 250.0,
            "Tail Index": 0.0,
            "Width Ratio": 4.0,
            "D10": 50.0,
            "D50": 100.0,
            "D90": 200.0,
            "Diameter Column": "Diameter (nm)",
            "Intensity Column": "Intensity (%)",
            "Volume Column": "Volume (%)",
            "Number Column": None,
            "Preferred Distribution": "Intensity (%)",
            "Z-Average Column": None,
            "PDI Column": None,
            "Scattering Angle Column": None,
            "Measurement Date": "2026-07-01 10:00:00",
        },
        warnings=["Moderate PDI"],
        source_text="raw export text",
    )

    measurement = measurement_from_dls_result(result)

    assert measurement.sample_name == "Batch A"
    assert measurement.metadata.source_files == ["batch_a.csv"]
    assert measurement.metadata.operator == "MT"
    assert measurement.summary_metrics.z_average == 105.5
    assert measurement.summary_metrics.pdi == 0.31
    assert measurement.distributions["particle_size"].diameter_nm == [50.0, 100.0, 200.0]
    assert measurement.distributions["particle_size"].intensity == [5.0, 100.0, 10.0]
    assert measurement.derived_metrics.d50_nm == 100.0
    assert measurement.derived_metrics.aggregation_risk == "Watch"
    assert measurement.flags[0].label == "Moderate PDI"
    assert measurement.flags[0].severity == "watch"
    assert measurement.flags[0].evidence == "PDI 0.31"
