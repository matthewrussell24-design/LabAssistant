from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

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
from labassistant.quality import classify_distribution_warnings


@dataclass
class ParsedDLSResult:
    name: str
    file_name: str
    data: pd.DataFrame
    metadata: dict[str, str]
    metrics: dict[str, float | str | None]
    warnings: list[str]
    source_text: str
    angle_summaries: list[dict] = field(default_factory=list)
    replicate_metrics: dict[str, list[float]] = field(default_factory=dict)


def read_uploaded_text(uploaded_file) -> str:
    """Read an uploaded file as text without permanently consuming the upload."""
    uploaded_file.seek(0)
    raw_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    for encoding in ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"]:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="replace")


def stringify_cell(value) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def make_unique_columns(columns: list[str]) -> list[str]:
    clean_columns = []
    seen = {}

    for index, column in enumerate(columns, start=1):
        clean_column = column.strip() or f"Column {index}"
        seen[clean_column] = seen.get(clean_column, 0) + 1

        if seen[clean_column] > 1:
            clean_column = f"{clean_column} {seen[clean_column]}"

        clean_columns.append(clean_column)

    return clean_columns


def convert_numeric_text(data: pd.DataFrame) -> pd.DataFrame:
    converted = data.copy()

    for column in converted.columns:
        if pd.api.types.is_numeric_dtype(converted[column]):
            continue

        cleaned = (
            converted[column]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        numeric_values = pd.to_numeric(cleaned, errors="coerce")
        numeric_ratio = numeric_values.notna().mean() if len(numeric_values) else 0

        if numeric_ratio >= 0.6:
            converted[column] = numeric_values

    return converted


def is_probably_number(value: str) -> bool:
    try:
        float(str(value).replace(",", "").replace("%", ""))
        return True
    except ValueError:
        return False


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:30])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        return dialect.delimiter
    except csv.Error:
        delimiter_counts = {delimiter: sample.count(delimiter) for delimiter in [",", "\t", ";", "|"]}
        return max(delimiter_counts, key=delimiter_counts.get)


def read_delimited_rows(text: str) -> list[list[str]]:
    delimiter = sniff_delimiter(text)
    reader = csv.reader(StringIO(text), delimiter=delimiter)
    return [[cell.strip() for cell in row] for row in reader]


def count_numeric_cells(row: list[str]) -> int:
    return sum(1 for cell in row if cell and is_probably_number(cell))


def has_distribution_header_signal(row: list[str]) -> bool:
    label = normalize_label(" ".join(row))
    header_terms = ["diameter", "particle size", "size nm", "radius", "intensity", "volume", "number"]
    return any(term in label for term in header_terms)


def normalize_row_width(row: list[str], column_count: int) -> list[str]:
    trimmed = trim_blank_tail(row)
    if len(trimmed) < column_count:
        return trimmed + [""] * (column_count - len(trimmed))
    return trimmed[:column_count]


def is_probable_zetasizer_measurement_row(row: list[str]) -> bool:
    cleaned = normalize_row_width(row, 6)
    return (
        len(cleaned) >= 6
        and is_probably_number(cleaned[0])
        and bool(cleaned[1].strip())
        and is_probably_number(cleaned[3])
        and is_probably_number(cleaned[4])
        and is_probably_number(cleaned[5])
    )


def find_loose_table_sections(rows: list[list[str]], sheet_name: str | None = None) -> list[dict]:
    sections = []
    label_prefix = f"{sheet_name}!" if sheet_name else ""

    for index, row in enumerate(rows):
        header = trim_blank_tail([cell.strip() for cell in row])
        column_count = len(header)

        if column_count < 2 or not any(header):
            continue
        if count_numeric_cells(header) >= max(1, column_count // 2):
            continue
        if not has_distribution_header_signal(header):
            continue

        table_rows = [header]
        skipped_non_numeric_rows = 0
        end_line = index + 1

        for next_index, next_row in enumerate(rows[index + 1 :], start=index + 2):
            cleaned_row = trim_blank_tail([cell.strip() for cell in next_row])

            if not any(cleaned_row):
                break

            compatible_width = len(cleaned_row) >= 2 and len(cleaned_row) >= column_count - 1
            numeric_count = count_numeric_cells(cleaned_row)

            if compatible_width and numeric_count > 0:
                table_rows.append(normalize_row_width(cleaned_row, column_count))
                end_line = next_index
                skipped_non_numeric_rows = 0
                continue

            if skipped_non_numeric_rows < 2 and numeric_count == 0:
                skipped_non_numeric_rows += 1
                continue

            break

        if len(table_rows) >= 3:
            sections.append(
                {
                    "start_line": index + 1,
                    "end_line": end_line,
                    "column_count": column_count,
                    "rows": table_rows,
                    "sheet_name": sheet_name,
                    "source_label": f"{label_prefix}{index + 1}",
                }
            )

    return sections


def find_table_sections(csv_text: str) -> list[dict]:
    rows = read_delimited_rows(csv_text)
    return find_table_sections_from_rows(rows)


def trim_blank_tail(row: list[str]) -> list[str]:
    trimmed = list(row)
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    return trimmed


def find_table_sections_from_rows(rows: list[list[str]], sheet_name: str | None = None) -> list[dict]:
    loose_sections = find_loose_table_sections(rows, sheet_name)
    if loose_sections:
        return loose_sections

    sections = []
    current_section = None

    for row_number, row in enumerate(rows, start=1):
        cleaned_row = trim_blank_tail([cell.strip() for cell in row])

        if not any(cleaned_row):
            current_section = None
            continue

        column_count = len(cleaned_row)
        label_prefix = f"{sheet_name}!" if sheet_name else ""

        if current_section is None or current_section["column_count"] != column_count:
            current_section = {
                "start_line": row_number,
                "end_line": row_number,
                "column_count": column_count,
                "rows": [cleaned_row],
                "sheet_name": sheet_name,
                "source_label": f"{label_prefix}{row_number}",
            }
            sections.append(current_section)
            continue

        current_section["rows"].append(cleaned_row)
        current_section["end_line"] = row_number

    return [section for section in sections if len(section["rows"]) >= 2]


def read_excel_sections(uploaded_file) -> tuple[list[dict], str]:
    uploaded_file.seek(0)
    workbook = pd.read_excel(BytesIO(uploaded_file.read()), sheet_name=None, header=None, dtype=object)
    uploaded_file.seek(0)

    sections = []
    preview_lines = []

    for sheet_name, sheet in workbook.items():
        rows = []
        preview_lines.append(f"Sheet: {sheet_name}")

        for _, row in sheet.iterrows():
            string_row = [stringify_cell(value) for value in row.tolist()]
            rows.append(string_row)
            preview_lines.append(",".join(trim_blank_tail(string_row)))

        sections.extend(find_table_sections_from_rows(rows, sheet_name))
        preview_lines.append("")

    return sections, "\n".join(preview_lines)


def section_to_dataframe(section: dict) -> pd.DataFrame:
    if section["column_count"] >= 6 and is_probable_zetasizer_measurement_row(section["rows"][0]):
        columns = ["Index", "Sample Name", "Measurement Date/Time", "Scattering Collection (°)", "Z-Average (nm)", "PDI"]
        rows = [normalize_row_width(row, len(columns)) for row in section["rows"]]
        return convert_numeric_text(pd.DataFrame(rows, columns=columns))

    columns = make_unique_columns(section["rows"][0])
    rows = [normalize_row_width(row, len(columns)) for row in section["rows"][1:]]
    data = pd.DataFrame(rows, columns=columns)
    return convert_numeric_text(data)


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def find_column(data: pd.DataFrame, includes: list[str], excludes: list[str] | None = None) -> str | None:
    excludes = excludes or []

    for column in data.columns:
        label = normalize_label(column)
        if all(term in label for term in includes) and not any(term in label for term in excludes):
            return column

    return None


def find_first_numeric_column(data: pd.DataFrame, candidates: list[list[str]]) -> str | None:
    numeric_columns = data.select_dtypes(include="number").columns.tolist()

    for terms in candidates:
        column = find_column(data, terms)
        if column in numeric_columns:
            return column

    return None


def first_nonempty_value(data: pd.DataFrame, column: str | None) -> str | None:
    if not column:
        return None

    values = data[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return None

    return values.iloc[0]


def format_measurement_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, (int, float)) and 20000 <= float(value) <= 80000:
        excel_epoch = datetime(1899, 12, 30)
        return (excel_epoch + timedelta(days=float(value))).strftime("%Y-%m-%d %H:%M:%S")

    text = str(value).strip()
    if not text:
        return None

    serial_match = re.fullmatch(r"\d+(?:\.\d+)?", text)
    if serial_match and 20000 <= float(text) <= 80000:
        excel_epoch = datetime(1899, 12, 30)
        return (excel_epoch + timedelta(days=float(text))).strftime("%Y-%m-%d %H:%M:%S")

    angle_suffix_match = re.match(r"(.+?\b(?:AM|PM))\s+\d+(?:\.\d+)?$", text, re.IGNORECASE)
    if angle_suffix_match:
        return angle_suffix_match.group(1)

    return text


def first_measurement_date(data: pd.DataFrame, column: str | None) -> str | None:
    if not column:
        return None

    for value in data[column].dropna().tolist():
        formatted = format_measurement_date(value)
        if formatted:
            return formatted

    return None


def most_common_value(data: pd.DataFrame, column: str | None) -> str | None:
    if not column:
        return None

    values = data[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return None

    return values.mode().iloc[0]


def extract_metadata(csv_text: str) -> dict[str, str]:
    metadata = {}

    for row in read_delimited_rows(csv_text):
        cleaned = [cell.strip() for cell in row if cell.strip()]

        if len(cleaned) == 2 and not is_probably_number(cleaned[0]):
            key, value = cleaned
            normalized = normalize_label(key)
            if any(term in normalized for term in ["sample", "date", "time", "temperature", "viscosity", "dispersant", "material", "operator"]):
                metadata[key] = value

    return metadata


def mean_column_value(data: pd.DataFrame, column: str | None) -> float | None:
    if not column:
        return None

    values = pd.to_numeric(data[column], errors="coerce").dropna()
    if values.empty:
        return None

    return float(values.mean())


def max_column_value(data: pd.DataFrame, column: str | None) -> float | None:
    if not column:
        return None

    values = pd.to_numeric(data[column], errors="coerce").dropna()
    if values.empty:
        return None

    return float(values.max())


def count_column_values(data: pd.DataFrame, column: str | None) -> int | None:
    if not column:
        return None

    return int(pd.to_numeric(data[column], errors="coerce").dropna().count())


def replicate_metric_values(data: pd.DataFrame, columns: dict[str, str | None]) -> dict[str, list[float]]:
    """Numeric replicate values in source order for columns parsed from summary exports."""
    replicates = {}
    for metric, column in columns.items():
        if not column or column not in data:
            continue
        values = pd.to_numeric(data[column], errors="coerce").dropna()
        if len(values) >= 2:
            replicates[metric] = [float(value) for value in values.tolist()]
    return replicates


def choose_distribution_section(sections: list[dict]) -> pd.DataFrame:
    dataframes = [section_to_dataframe(section) for section in sections]

    def score(data: pd.DataFrame) -> float:
        diameter = infer_diameter_column(data)
        intensity = infer_distribution_column(data, "Intensity")
        volume = infer_distribution_column(data, "Volume")
        number = infer_distribution_column(data, "Number")
        numeric_count = len(data.select_dtypes(include="number").columns)
        return (
            (30 if diameter else 0)
            + (20 if intensity else 0)
            + (12 if volume else 0)
            + (12 if number else 0)
            + min(len(data), 200) / 20
            + numeric_count
        )

    return max(dataframes, key=score)


def infer_diameter_column(data: pd.DataFrame) -> str | None:
    return find_first_numeric_column(
        data,
        [
            ["diameter"],
            ["d", "nm"],
            ["size", "nm"],
            ["particle", "size"],
            ["size"],
            ["radius"],
        ],
    )


def infer_distribution_column(data: pd.DataFrame, mode: str) -> str | None:
    mode_terms = {
        "Intensity": [["intensity"], ["weighted", "intensity"]],
        "Volume": [["volume"]],
        "Number": [["number"]],
    }
    return find_first_numeric_column(data, mode_terms[mode])


def infer_z_average_column(data: pd.DataFrame) -> str | None:
    return find_first_numeric_column(data, [["z", "average"], ["z", "avg"]])


def infer_pdi_column(data: pd.DataFrame) -> str | None:
    return find_first_numeric_column(data, [["pdi"], ["poly", "dispers"]])


def infer_scattering_angle_column(data: pd.DataFrame) -> str | None:
    return find_first_numeric_column(data, [["scattering"], ["angle"]])


def infer_sample_name_column(data: pd.DataFrame) -> str | None:
    return find_column(data, ["sample", "name"]) or find_column(data, ["sample"])


def infer_measurement_date_column(data: pd.DataFrame) -> str | None:
    return find_column(data, ["measurement", "date"]) or find_column(data, ["date"])


def infer_summary_metric_name_column(data: pd.DataFrame) -> str | None:
    for column in data.columns:
        label = normalize_label(column)
        if label in {"name", "metric", "parameter"}:
            return column
    return None


def infer_summary_value_column(data: pd.DataFrame) -> str | None:
    for terms in [["mean"], ["average"], ["avg"], ["all"]]:
        column = find_column(data, terms)
        if column in data.columns:
            return column
    return None


def is_summary_stats_table(data: pd.DataFrame) -> bool:
    metric_column = infer_summary_metric_name_column(data)
    value_column = infer_summary_value_column(data)
    if not metric_column or not value_column:
        return False

    metric_labels = data[metric_column].dropna().astype(str).map(normalize_label).tolist()
    has_z_average = any("z average" in label or "z avg" in label for label in metric_labels)
    has_pdi = any("pdi" in label or "polydispersity" in label or "polydispersity index" in label for label in metric_labels)
    return has_z_average or has_pdi


def extract_summary_metric(data: pd.DataFrame, metric_patterns: list[str], value_column: str | None = None) -> float | None:
    metric_column = infer_summary_metric_name_column(data)
    value_column = value_column or infer_summary_value_column(data)
    if not metric_column or not value_column:
        return None

    for _, row in data.iterrows():
        metric_name = str(row.get(metric_column, ""))
        if any(re.search(pattern, metric_name, re.IGNORECASE) for pattern in metric_patterns):
            value = pd.to_numeric(pd.Series([row.get(value_column)]), errors="coerce").dropna()
            if not value.empty:
                return float(value.iloc[0])

    return None


def extract_summary_stat(data: pd.DataFrame, metric_patterns: list[str], stat_column_terms: list[str]) -> float | None:
    metric_column = infer_summary_metric_name_column(data)
    stat_column = None
    for terms in [stat_column_terms]:
        stat_column = find_column(data, terms)
        if stat_column:
            break

    if not metric_column or not stat_column:
        return None

    for _, row in data.iterrows():
        metric_name = str(row.get(metric_column, ""))
        if any(re.search(pattern, metric_name, re.IGNORECASE) for pattern in metric_patterns):
            value = pd.to_numeric(pd.Series([row.get(stat_column)]), errors="coerce").dropna()
            if not value.empty:
                return float(value.iloc[0])

    return None


def extract_scalar_metric(data: pd.DataFrame, csv_text: str, metric_patterns: list[str]) -> float | None:
    columns = list(data.columns)

    for pattern in metric_patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for column in columns:
            if regex.search(column):
                values = pd.to_numeric(data[column], errors="coerce").dropna()
                if not values.empty:
                    return float(values.iloc[0])

    for line in csv_text.splitlines():
        for pattern in metric_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                values = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line)
                if values:
                    return float(values[-1])

    return None


def summarize_by_angle(
    data: pd.DataFrame,
    scattering_column: str | None,
    z_average_column: str | None,
    pdi_column: str | None,
) -> list[dict]:
    """Aggregate a per-measurement replicate table by scattering angle.

    Dual-angle Zetasizer runs interleave forward and back measurements in one
    table. Grouping by the reported angle is robust to any ordering (some lots
    are not cleanly alternating), so each angle gets its own count, mean
    Z-average, mean PDI, and max Z-average.
    """
    if not scattering_column or not (z_average_column or pdi_column):
        return []

    angles = pd.to_numeric(data[scattering_column], errors="coerce")
    distinct_angles = sorted(angles.dropna().unique().tolist())
    if len(distinct_angles) < 2:
        return []

    summaries = []
    for angle in distinct_angles:
        rows = data.loc[angles == angle]
        z_values = pd.to_numeric(rows[z_average_column], errors="coerce").dropna() if z_average_column else pd.Series(dtype=float)
        pdi_values = pd.to_numeric(rows[pdi_column], errors="coerce").dropna() if pdi_column else pd.Series(dtype=float)
        summaries.append(
            {
                "angle_degrees": float(angle),
                "position": "forward" if angle < 90 else "back",
                "count": int(len(rows)),
                "z_average": float(z_values.mean()) if not z_values.empty else None,
                "pdi": float(pdi_values.mean()) if not pdi_values.empty else None,
                "max_z_average": float(z_values.max()) if not z_values.empty else None,
            }
        )

    return summaries


def source_stem(uploaded_file) -> str:
    return Path(uploaded_file.name).stem


def parse_dls_upload(uploaded_file) -> ParsedDLSResult:
    file_extension = Path(uploaded_file.name).suffix.lower()

    if file_extension in [".xlsx", ".xls"]:
        sections, source_text = read_excel_sections(uploaded_file)
    else:
        source_text = read_uploaded_text(uploaded_file)
        sections = find_table_sections(source_text)

    if not sections:
        raise pd.errors.EmptyDataError("No table-like sections were found.")

    data = choose_distribution_section(sections)
    metadata = extract_metadata(source_text)
    sample_name_column = infer_sample_name_column(data)
    measurement_date_column = infer_measurement_date_column(data)
    name = metadata.get("Sample Name") or metadata.get("Sample") or most_common_value(data, sample_name_column) or source_stem(uploaded_file)

    diameter_column = infer_diameter_column(data)
    intensity_column = infer_distribution_column(data, "Intensity")
    volume_column = infer_distribution_column(data, "Volume")
    number_column = infer_distribution_column(data, "Number")
    preferred_distribution = intensity_column or volume_column or number_column
    z_average_column = infer_z_average_column(data)
    pdi_column = infer_pdi_column(data)
    scattering_angle_column = infer_scattering_angle_column(data)
    has_summary_stats = is_summary_stats_table(data)
    has_distribution_curve = bool(diameter_column and preferred_distribution)
    has_repeated_measurements = (bool(z_average_column or pdi_column) or has_summary_stats) and not has_distribution_curve
    peaks = find_local_peaks(data, diameter_column, preferred_distribution)

    if has_summary_stats:
        z_average = extract_summary_metric(data, [r"\bz[-\s]?average\b", r"\bz[-\s]?avg\b"])
        pdi = extract_summary_metric(data, [r"\bpdi\b", r"poly.*dispers"])
    elif has_repeated_measurements:
        z_average = mean_column_value(data, z_average_column)
        pdi = mean_column_value(data, pdi_column)
    else:
        z_average = extract_scalar_metric(data, source_text, [r"\bz[-\s]?average\b", r"\bz[-\s]?avg\b"])
        pdi = extract_scalar_metric(data, source_text, [r"\bpdi\b", r"poly.*dispers"])

    count_rate = extract_scalar_metric(data, source_text, [r"count\s*rate", r"kcps"])
    tail_index = calculate_tail_index(data, diameter_column, preferred_distribution)
    width_ratio = calculate_width_ratio(data, diameter_column, preferred_distribution)
    peak_count = count_peaks(data, diameter_column, preferred_distribution)
    peak_width_ratio = calculate_peak_width(data, diameter_column, preferred_distribution)
    peak_symmetry = calculate_peak_symmetry(data, diameter_column, preferred_distribution)
    skewness = calculate_log_skewness(data, diameter_column, preferred_distribution)
    percentiles = calculate_distribution_percentiles(data, diameter_column, preferred_distribution)
    measurement_count = count_column_values(data, z_average_column or pdi_column)
    max_pdi = extract_summary_stat(data, [r"\bpdi\b", r"poly.*dispers"], ["maximum"]) if has_summary_stats else max_column_value(data, pdi_column)
    max_z_average = extract_summary_stat(data, [r"\bz[-\s]?average\b", r"\bz[-\s]?avg\b"], ["maximum"]) if has_summary_stats else max_column_value(data, z_average_column)
    replicate_metrics = replicate_metric_values(
        data,
        {
            "Z-Average": z_average_column,
            "PDI": pdi_column,
        },
    ) if has_repeated_measurements else {}
    scattering_angles = []
    if scattering_angle_column:
        scattering_angles = sorted(pd.to_numeric(data[scattering_angle_column], errors="coerce").dropna().unique().tolist())

    primary_peak = peaks[0]["diameter"] if peaks else None
    secondary_peak = peaks[1]["diameter"] if len(peaks) > 1 else None

    aggregation_risk = assess_aggregation_risk(
        tail_index=tail_index,
        secondary_peak_nm=secondary_peak,
        primary_peak_nm=primary_peak,
        pdi=pdi,
        log_skewness=skewness,
        width_ratio=width_ratio,
    )
    quality_score = calculate_quality_score(
        pdi=pdi,
        tail_index=tail_index,
        width_ratio=width_ratio,
        secondary_peak_nm=secondary_peak,
    )

    warnings = classify_distribution_warnings(
        pdi=pdi,
        secondary_peak=secondary_peak,
        tail_index=tail_index,
        width_ratio=width_ratio,
        has_repeated_measurements=has_repeated_measurements,
        has_distribution_columns=bool(diameter_column and preferred_distribution),
    )

    metrics = {
        "Data Type": "Measurement Summary" if has_repeated_measurements else "Distribution Curve",
        "Z-Average": z_average,
        "PDI": pdi,
        "Max Z-Average": max_z_average,
        "Max PDI": max_pdi,
        "Measurement Count": measurement_count,
        "Scattering Angles": ", ".join(f"{angle:g}°" for angle in scattering_angles) if scattering_angles else None,
        "Primary Peak": primary_peak,
        "Secondary Peak": secondary_peak,
        "Peak Count": peak_count,
        "Peak Width Ratio": peak_width_ratio,
        "Peak Symmetry": peak_symmetry,
        "Count Rate": count_rate,
        "Tail Index": tail_index,
        "Width Ratio": width_ratio,
        "Skewness": skewness,
        "Aggregation Risk": aggregation_risk,
        "Quality Score": quality_score,
        "D10": percentiles["D10"],
        "D50": percentiles["D50"],
        "D90": percentiles["D90"],
        "Diameter Column": diameter_column,
        "Intensity Column": intensity_column,
        "Volume Column": volume_column,
        "Number Column": number_column,
        "Preferred Distribution": preferred_distribution,
        "Z-Average Column": z_average_column,
        "PDI Column": pdi_column,
        "Scattering Angle Column": scattering_angle_column,
        "Measurement Date": metadata.get("Measurement Date") or metadata.get("Date") or metadata.get("Measurement Date and Time") or first_measurement_date(data, measurement_date_column),
    }

    angle_summaries = (
        summarize_by_angle(data, scattering_angle_column, z_average_column, pdi_column)
        if has_repeated_measurements
        else []
    )

    return ParsedDLSResult(
        name=str(name),
        file_name=uploaded_file.name,
        data=data,
        metadata=metadata,
        metrics=metrics,
        warnings=warnings,
        source_text=source_text,
        angle_summaries=angle_summaries,
        replicate_metrics=replicate_metrics,
    )
