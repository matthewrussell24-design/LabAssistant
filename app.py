from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from labassistant.aggregation import (
    INDEX_ELEVATED,
    INDEX_WATCH,
    assess_dual_angle_aggregation,
)
from labassistant.interpretation import (
    build_ai_summary,
    build_data_analysis,
    build_decision_brief,
    format_metric,
    review_evidence,
)
from labassistant.importers.measurement_importer import build_import_preview, import_measurement_groups
from labassistant.history import (
    compare_experiments,
    find_similar_samples,
    history_table,
    latest_experiment,
    load_history,
    save_experiment,
    trend_table,
)
from labassistant.metrics import (
    find_local_peaks,
)
from labassistant.quality import (
    REVIEW_WARNINGS,
    SIGNAL_WARNINGS,
    STATUS_NORMAL,
    STATUS_REVIEW,
    STATUS_WATCH,
)
from labassistant.view_models import (
    ParsedSample,
    build_angle_table,
    build_metrics_table,
    sample_from_measurement,
    sample_status,
)


def render_metric_row(label: str, value: str) -> str:
    return (
        '<div class="metric-row">'
        f'<span class="metric-label">{html.escape(label)}</span>'
        f'<span class="metric-value">{html.escape(value)}</span>'
        "</div>"
    )


def dashboard_health_score(samples: list[ParsedSample]) -> int:
    if not samples:
        return 0

    status_weights = {
        STATUS_NORMAL: 100,
        STATUS_WATCH: 65,
        STATUS_REVIEW: 25,
    }
    score = sum(status_weights.get(sample_status(sample), 50) for sample in samples) / len(samples)
    return int(round(score))


def render_health_strip(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    flagged_count = sum(sample_status(sample) != STATUS_NORMAL for sample in samples)
    review_count = sum(sample_status(sample) == STATUS_REVIEW for sample in samples)
    median_z = metrics["Z-Average"].dropna().median() if "Z-Average" in metrics else None
    median_tail = metrics["Tail Index"].dropna().median() if "Tail Index" in metrics else None

    top_cols = st.columns(5)
    top_cols[0].metric("Health Score", f"{dashboard_health_score(samples)}/100")
    top_cols[1].metric("Samples", len(samples))
    top_cols[2].metric("Flagged", flagged_count, delta=f"{review_count} review" if review_count else None)
    top_cols[3].metric("Median Z-Average", format_metric(median_z, "nm") if pd.notna(median_z) else "Not found")
    top_cols[4].metric("Median tail >1,000 nm", format_metric(median_tail, "%") if pd.notna(median_tail) else "Not found")


def render_data_analysis(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    analysis = build_data_analysis(samples, metrics)

    st.subheader("Data Analysis")
    st.caption("Dataset-specific interpretation of which samples and metrics are shaping the result.")

    analysis_columns = st.columns(3)
    for column, (title, items) in zip(analysis_columns, analysis.items()):
        with column:
            st.markdown(
                f"""
                <div class="analysis-card">
                    <div class="summary-title">{html.escape(title)}</div>
                    <ul>
                        {''.join(f'<li>{html.escape(item)}</li>' for item in items)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_ai_summary(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    summary = build_ai_summary(samples, metrics)

    st.subheader("Automated Findings")
    st.caption("Rule-based summary generated from the parsed metrics (not a language model).")

    summary_columns = st.columns(min(3, len(summary)))
    for index, (title, items) in enumerate(summary.items()):
        column = summary_columns[index % len(summary_columns)]
        with column:
            st.markdown(
                f"""
                <div class="summary-card">
                    <div class="summary-title">{html.escape(title)}</div>
                    <ul>
                        {''.join(f'<li>{html.escape(item)}</li>' for item in items)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_decision_brief(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    decision = build_decision_brief(samples, metrics)
    attention = decision["attention"]
    flagged = attention[attention["Status"] != STATUS_NORMAL]

    st.subheader("Decision Brief")

    decision_cols = st.columns([1.1, 1.1, 0.8, 2.2])
    for column, label, value in [
        (decision_cols[0], "Best Sample", str(decision["best"])),
        (decision_cols[1], "Needs Attention", str(decision["worst"])),
        (decision_cols[2], "Flagged", str(decision["flagged"])),
    ]:
        column.markdown(
            f"""
            <div class="decision-card">
                <div class="decision-label">{html.escape(label)}</div>
                <div class="decision-value">{html.escape(value)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    decision_cols[3].markdown(
        f"""
        <div class="decision-card">
            <div class="decision-label">Next Check</div>
            <div class="decision-text">{html.escape(str(decision["next_check"]))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if flagged.empty:
        st.success("Current read: the parsed samples look okay by the active DLS warning rules.")
    else:
        st.warning(f"Current read: inspect {flagged.iloc[0]['Sample']} first; {flagged.iloc[0]['Reason']}.")

    with st.expander("Attention ranking", expanded=not flagged.empty):
        display = attention.copy()
        display["Attention Score"] = display["Attention Score"].round(1)
        st.dataframe(display[["Sample", "Status", "Attention Score", "Reason", "Warnings"]], use_container_width=True, hide_index=True)


def render_decision_workbench(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    render_decision_brief(samples, metrics)
    render_health_strip(samples, metrics)

    finding_col, review_col = st.columns([1.45, 1])
    with finding_col:
        render_ai_summary(samples, metrics)
    with review_col:
        st.subheader("Samples To Inspect")
        render_aggregation_review(samples)


def add_page_style() -> None:
    st.set_page_config(page_title="LabAssistant", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --lab-border: #d7dde7;
            --lab-muted: #64748b;
            --lab-text: #172033;
            --lab-panel: #ffffff;
            --lab-soft: #f6f8fb;
            --lab-accent: #2563eb;
            --lab-watch: #b45309;
            --lab-review: #b91c1c;
            --lab-normal: #047857;
        }
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 {
            color: var(--lab-text);
            letter-spacing: 0;
        }
        [data-testid="stMetric"] {
            background: var(--lab-panel);
            border: 1px solid var(--lab-border);
            border-radius: 8px;
            padding: 0.7rem 0.8rem;
        }
        .sample-card {
            border: 1px solid var(--lab-border);
            border-left: 5px solid #94a3b8;
            border-radius: 8px;
            background: var(--lab-panel);
            padding: 0.85rem;
            min-height: 190px;
        }
        .sample-card.normal {
            border-left-color: var(--lab-normal);
        }
        .sample-card.watch {
            border-left-color: var(--lab-watch);
        }
        .sample-card.review {
            border-left-color: var(--lab-review);
        }
        .sample-title {
            font-weight: 700;
            font-size: 1rem;
            color: var(--lab-text);
            margin-bottom: 0.45rem;
            overflow-wrap: anywhere;
        }
        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.5rem;
            font-size: 0.75rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
            background: #eef2f7;
            color: #334155;
        }
        .status-normal {
            background: #dff7ec;
            color: var(--lab-normal);
        }
        .status-watch {
            background: #fef3c7;
            color: var(--lab-watch);
        }
        .status-review {
            background: #fee2e2;
            color: var(--lab-review);
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            border-top: 1px solid #edf1f5;
            padding-top: 0.32rem;
            margin-top: 0.32rem;
            font-size: 0.88rem;
        }
        .metric-label {
            color: var(--lab-muted);
        }
        .metric-value {
            color: var(--lab-text);
            font-weight: 650;
            text-align: right;
        }
        .review-card {
            border: 1px solid var(--lab-border);
            border-radius: 8px;
            background: var(--lab-soft);
            padding: 0.9rem;
            margin-bottom: 0.65rem;
        }
        .review-title {
            font-weight: 750;
            color: var(--lab-text);
        }
        .review-signals {
            color: var(--lab-muted);
            margin-top: 0.3rem;
        }
        .decision-card {
            border: 1px solid var(--lab-border);
            border-radius: 8px;
            background: #f8fbff;
            padding: 0.72rem 0.85rem;
            min-height: 86px;
        }
        .decision-label {
            color: var(--lab-muted);
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.24rem;
            text-transform: uppercase;
        }
        .decision-value {
            color: var(--lab-text);
            font-size: 1.05rem;
            font-weight: 760;
            overflow-wrap: anywhere;
            line-height: 1.25;
        }
        .decision-text {
            color: var(--lab-muted);
            line-height: 1.38;
        }
        .summary-card {
            border: 1px solid var(--lab-border);
            border-radius: 8px;
            background: var(--lab-panel);
            padding: 0.9rem 1rem;
            min-height: 190px;
        }
        .summary-title {
            color: var(--lab-text);
            font-weight: 750;
            margin-bottom: 0.55rem;
        }
        .summary-card ul {
            margin: 0;
            padding-left: 1.05rem;
        }
        .summary-card li {
            color: var(--lab-muted);
            margin-bottom: 0.45rem;
            line-height: 1.42;
        }
        .analysis-card {
            border: 1px solid var(--lab-border);
            border-radius: 8px;
            background: #f8fbff;
            padding: 0.9rem 1rem;
            min-height: 220px;
        }
        .analysis-card ul {
            margin: 0;
            padding-left: 1.05rem;
        }
        .analysis-card li {
            color: var(--lab-muted);
            margin-bottom: 0.45rem;
            line-height: 1.42;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sample_card(sample: ParsedSample) -> None:
    status = sample_status(sample)
    status_class = status.lower()
    sample_name = html.escape(sample.name)
    warnings = ", ".join(sample.warnings) if sample.warnings else "No flags"
    card_class = "normal" if status == STATUS_NORMAL else "watch" if status == STATUS_WATCH else "review"
    rows = [
        ("Type", sample.metrics["Data Type"]),
        ("Z-Average", format_metric(sample.metrics["Z-Average"], "nm")),
        ("PDI", format_metric(sample.metrics["PDI"], digits=3)),
        ("Measurements", format_metric(sample.metrics["Measurement Count"], digits=0)),
        ("Angles", str(sample.metrics["Scattering Angles"] or "Not found")),
    ]
    if sample.metrics.get("Primary Peak") is not None and pd.notna(sample.metrics.get("Primary Peak")):
        rows.append(("Primary Peak", format_metric(sample.metrics["Primary Peak"], "nm")))
    if sample.metrics.get("Tail Index") is not None and pd.notna(sample.metrics.get("Tail Index")):
        rows.append(("Tail >1,000 nm", format_metric(sample.metrics["Tail Index"], "%")))
    rows.append(("Review signals", warnings))
    metric_rows = "\n".join(render_metric_row(label, value) for label, value in rows)

    st.markdown(
        f"""
        <div class="sample-card {card_class}">
            <div class="sample-title">{sample_name}</div>
            <span class="status-pill status-{status_class}">{status}</span>
            {metric_rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_distribution_column(sample: ParsedSample, mode: str) -> str | None:
    # Return only the requested signal's column. No cross-signal fallback, so a
    # missing Volume/Number curve shows a clean empty state instead of intensity
    # data mislabeled as volume/number.
    return {
        "Intensity": sample.metrics["Intensity Column"],
        "Volume": sample.metrics["Volume Column"],
        "Number": sample.metrics["Number Column"],
    }.get(mode)


def available_signals(samples: list[ParsedSample]) -> list[str]:
    """Distribution signals that actually have data across the imported samples."""
    present = [
        mode
        for mode in ("Intensity", "Volume", "Number")
        if any(get_distribution_column(sample, mode) for sample in samples)
    ]
    return present or ["Intensity"]


def get_distribution_data(sample: ParsedSample, distribution_mode: str, normalize: bool = True) -> pd.DataFrame:
    diameter_column = sample.metrics["Diameter Column"]
    distribution_column = get_distribution_column(sample, distribution_mode)

    if not diameter_column or not distribution_column:
        return pd.DataFrame(columns=["Diameter", "Signal"])

    working = sample.data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
    working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

    if working.empty:
        return pd.DataFrame(columns=["Diameter", "Signal"])

    signal = working[distribution_column]
    if normalize and signal.max() > 0:
        signal = signal / signal.max() * 100

    return pd.DataFrame({"Diameter": working[diameter_column].astype(float), "Signal": signal.astype(float)})


def render_distribution_chart(samples: list[ParsedSample], selected_names: list[str], distribution_mode: str, normalize: bool, show_peaks: bool, reference_name: str | None) -> None:
    figure = go.Figure()
    selected = [sample for sample in samples if sample.name in selected_names]
    reference_name = reference_name if reference_name and reference_name != "None" else None
    y_label = f"Normalized {distribution_mode}" if normalize else distribution_mode

    for sample in selected:
        diameter_column = sample.metrics["Diameter Column"]
        distribution_column = get_distribution_column(sample, distribution_mode)

        if not diameter_column or not distribution_column:
            continue

        working = sample.data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
        working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]

        if working.empty:
            continue

        y_values = working[distribution_column]

        if normalize and y_values.max() > 0:
            y_values = y_values / y_values.max() * 100

        is_reference = sample.name == reference_name
        figure.add_trace(
            go.Scatter(
                x=working[diameter_column],
                y=y_values,
                mode="lines",
                name=sample.name,
                line={"width": 4 if is_reference else 2.2},
                opacity=1 if is_reference or not reference_name else 0.72,
                hovertemplate="<b>%{fullData.name}</b><br>Diameter: %{x:.3g} nm<br>Signal: %{y:.3g}<extra></extra>",
            )
        )

        if show_peaks:
            peaks = find_local_peaks(working, diameter_column, distribution_column)
            for peak_index, peak in enumerate(peaks[:2]):
                y_peak = peak["value"]
                if normalize and y_values.max() > 0:
                    original_max = working[distribution_column].max()
                    y_peak = y_peak / original_max * 100 if original_max else y_peak

                figure.add_trace(
                    go.Scatter(
                        x=[peak["diameter"]],
                        y=[y_peak],
                        mode="markers+text" if peak_index == 0 else "markers",
                        name=f"{sample.name} peak",
                        marker={"size": 8 if peak_index == 0 else 7, "symbol": "diamond" if peak_index == 0 else "circle-open"},
                        text=[f"{peak['diameter']:.0f} nm"] if peak_index == 0 else None,
                        textposition="top center",
                        showlegend=False,
                        hovertemplate=f"<b>{sample.name}</b><br>Peak: {peak['diameter']:.3g} nm<br>Signal: {peak['value']:.3g}<extra></extra>",
                    )
                )

    figure.add_vrect(
        x0=1000,
        x1=100000,
        fillcolor="#f59e0b",
        opacity=0.08,
        line_width=0,
        annotation_text="large-particle region",
        annotation_position="top left",
    )
    figure.update_layout(
        template="plotly_white",
        height=540,
        margin={"l": 52, "r": 24, "t": 42, "b": 56},
        title={"text": "Particle Size Distribution", "x": 0.015, "xanchor": "left"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="closest",
        xaxis={
            "title": "Diameter (nm)",
            "type": "log",
            "showgrid": True,
            "gridcolor": "#e8eef5",
            "rangeslider": {"visible": False},
        },
        yaxis={"title": y_label, "gridcolor": "#e8eef5"},
    )

    if not figure.data:
        st.info("No usable distribution points were found for the selected samples.")
        return

    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})


def render_difference_chart(samples: list[ParsedSample], selected_names: list[str], distribution_mode: str, reference_name: str | None) -> None:
    if not reference_name or reference_name == "None":
        st.info("Choose a reference sample to see distribution differences.")
        return

    reference = next((sample for sample in samples if sample.name == reference_name), None)
    if reference is None:
        st.info("Choose a valid reference sample to see distribution differences.")
        return

    reference_data = get_distribution_data(reference, distribution_mode, normalize=True)
    if reference_data.empty:
        st.info("The reference sample does not have usable distribution points.")
        return

    figure = go.Figure()
    selected = [sample for sample in samples if sample.name in selected_names and sample.name != reference_name]

    for sample in selected:
        sample_data = get_distribution_data(sample, distribution_mode, normalize=True)
        if sample_data.empty:
            continue

        merged = pd.merge_asof(
            sample_data.sort_values("Diameter"),
            reference_data.sort_values("Diameter"),
            on="Diameter",
            direction="nearest",
            suffixes=("", "_Reference"),
        ).dropna()

        if merged.empty:
            continue

        figure.add_trace(
            go.Scatter(
                x=merged["Diameter"],
                y=merged["Signal"] - merged["Signal_Reference"],
                mode="lines",
                name=sample.name,
                hovertemplate="<b>%{fullData.name}</b><br>Diameter: %{x:.3g} nm<br>Delta signal: %{y:.3g}<extra></extra>",
            )
        )

    figure.add_hline(y=0, line_color="#475569", line_width=1)
    figure.add_vrect(x0=1000, x1=100000, fillcolor="#f59e0b", opacity=0.08, line_width=0)
    figure.update_layout(
        template="plotly_white",
        height=430,
        margin={"l": 52, "r": 24, "t": 42, "b": 56},
        title={"text": f"Difference from {reference_name}", "x": 0.015, "xanchor": "left"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        xaxis={"title": "Diameter (nm)", "type": "log", "gridcolor": "#e8eef5"},
        yaxis={"title": "Normalized signal delta", "gridcolor": "#e8eef5", "zeroline": True},
        hovermode="closest",
    )

    if not figure.data:
        st.info("No selected non-reference samples have usable distribution points.")
        return

    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})


def metric_dot_plot(metrics: pd.DataFrame, metric: str, title: str, unit: str = "", threshold: float | None = None, log_x: bool = False) -> go.Figure:
    figure = go.Figure()

    if metric not in metrics.columns:
        figure.update_layout(template="plotly_white", height=290, title=title)
        return figure

    working = metrics.dropna(subset=[metric]).sort_values(metric)

    if working.empty:
        figure.update_layout(template="plotly_white", height=290, title=title)
        return figure

    colors = working["Status"].map({STATUS_NORMAL: "#047857", STATUS_WATCH: "#b45309", STATUS_REVIEW: "#b91c1c"}).fillna("#2563eb")

    figure.add_trace(
        go.Scatter(
            x=working[metric],
            y=working["Sample"],
            mode="markers",
            marker={"size": 12, "color": colors},
            text=working["Warnings"],
            hovertemplate="<b>%{y}</b><br>%{x:.3g} " + unit + "<br>%{text}<extra></extra>",
        )
    )

    if threshold is not None:
        figure.add_vline(x=threshold, line_dash="dash", line_color="#b45309", annotation_text=f"Review {threshold:g}")

    figure.update_layout(
        template="plotly_white",
        height=max(280, 32 * len(working) + 110),
        margin={"l": 100, "r": 28, "t": 44, "b": 42},
        title={"text": title, "x": 0.015, "xanchor": "left"},
        xaxis={"title": f"{metric} {unit}".strip(), "type": "log" if log_x else "linear", "gridcolor": "#e8eef5"},
        yaxis={"title": ""},
        showlegend=False,
    )
    return figure


def render_metric_dot_plot(metrics: pd.DataFrame, metric: str, title: str, unit: str = "", threshold: float | None = None, log_x: bool = False) -> None:
    if metric not in metrics.columns or metrics.dropna(subset=[metric]).empty:
        st.info(f"No {title} values were found for the imported samples.")
        return
    st.plotly_chart(metric_dot_plot(metrics, metric, title, unit, threshold, log_x), use_container_width=True, config={"displaylogo": False})


def render_peak_plot(metrics: pd.DataFrame) -> None:
    rows = []
    for _, row in metrics.iterrows():
        if pd.notna(row["Primary Peak"]):
            rows.append({"Sample": row["Sample"], "Peak": row["Primary Peak"], "Type": "Primary", "Status": row["Status"], "Warnings": row["Warnings"]})
        if pd.notna(row["Secondary Peak"]):
            rows.append({"Sample": row["Sample"], "Peak": row["Secondary Peak"], "Type": "Secondary", "Status": row["Status"], "Warnings": row["Warnings"]})

    peak_data = pd.DataFrame(rows)
    if peak_data.empty:
        st.info("No primary or secondary peak values were found for the imported samples.")
        return

    figure = go.Figure()

    for peak_type, symbol in [("Primary", "circle"), ("Secondary", "circle-open")]:
        subset = peak_data[peak_data["Type"] == peak_type]
        if subset.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=subset["Peak"],
                y=subset["Sample"],
                mode="markers",
                name=peak_type,
                marker={"size": 13, "symbol": symbol},
                text=subset["Warnings"],
                hovertemplate="<b>%{y}</b><br>%{fullData.name} peak: %{x:.3g} nm<br>%{text}<extra></extra>",
            )
        )

    figure.update_layout(
        template="plotly_white",
        height=max(280, 32 * max(len(metrics), 1) + 110),
        margin={"l": 100, "r": 28, "t": 44, "b": 42},
        title={"text": "Peak Diameter", "x": 0.015, "xanchor": "left"},
        xaxis={"title": "Diameter (nm)", "type": "log", "gridcolor": "#e8eef5"},
        yaxis={"title": ""},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


def render_distribution_spread_plot(metrics: pd.DataFrame) -> None:
    working = metrics.dropna(subset=["D10", "D50", "D90"]).sort_values("D50")
    if working.empty:
        st.info("No D10/D50/D90 values were found for distribution width review.")
        return

    figure = go.Figure()

    colors = working["Status"].map({STATUS_NORMAL: "#047857", STATUS_WATCH: "#b45309", STATUS_REVIEW: "#b91c1c"}).fillna("#2563eb")
    for _, row in working.iterrows():
        figure.add_trace(
            go.Scatter(
                x=[row["D10"], row["D90"]],
                y=[row["Sample"], row["Sample"]],
                mode="lines",
                line={"color": "#94a3b8", "width": 5},
                showlegend=False,
                hoverinfo="skip",
            )
        )
    figure.add_trace(
        go.Scatter(
            x=working["D50"],
            y=working["Sample"],
            mode="markers",
            marker={"size": 13, "color": colors, "line": {"color": "white", "width": 1}},
            text=working.apply(lambda row: f"D10 {row['D10']:.3g} nm, D50 {row['D50']:.3g} nm, D90 {row['D90']:.3g} nm", axis=1),
            showlegend=False,
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
    )

    figure.update_layout(
        template="plotly_white",
        height=max(280, 32 * max(len(working), 1) + 110),
        margin={"l": 100, "r": 28, "t": 44, "b": 42},
        title={"text": "Distribution Width (D10-D90, D50 marker)", "x": 0.015, "xanchor": "left"},
        xaxis={"title": "Diameter (nm)", "type": "log", "gridcolor": "#e8eef5"},
        yaxis={"title": ""},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


def render_signal_matrix(metrics: pd.DataFrame) -> None:
    signals = SIGNAL_WARNINGS
    samples = metrics["Sample"].tolist()
    values = []
    hover_text = []

    for _, row in metrics.iterrows():
        warnings = row["Warnings"] if isinstance(row["Warnings"], str) else ""
        row_values = []
        row_hover = []
        for signal in signals:
            present = signal in warnings
            row_values.append(1 if present else 0)
            row_hover.append(f"{row['Sample']}<br>{signal}: {'present' if present else 'not detected'}")
        values.append(row_values)
        hover_text.append(row_hover)

    figure = go.Figure(
        data=go.Heatmap(
            z=values,
            x=signals,
            y=samples,
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            colorscale=[[0, "#f1f5f9"], [1, "#f97316"]],
            showscale=False,
            xgap=2,
            ygap=2,
        )
    )
    figure.update_layout(
        template="plotly_white",
        height=max(260, 30 * max(len(samples), 1) + 120),
        margin={"l": 108, "r": 20, "t": 44, "b": 78},
        title={"text": "Warning Signal Matrix", "x": 0.015, "xanchor": "left"},
        xaxis={"side": "bottom"},
        yaxis={"title": ""},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


def render_correlogram_quality_chart(samples: list[ParsedSample]) -> None:
    rows = []
    for sample in samples:
        for point in sample.measurement.correlogram:
            rows.append(
                {
                    "Sample": sample.name,
                    "Delay Time": point.get("delay_time"),
                    "Correlation": point.get("correlation"),
                    "Replicate": point.get("replicate"),
                    "Noise Score": sample.measurement.derived_metrics.correlogram_noise_score,
                }
            )

    data = pd.DataFrame(rows)
    if data.empty:
        st.info("No correlogram data was found for signal-quality review.")
        return

    figure = go.Figure()
    for sample_name, sample_data in data.groupby("Sample", sort=False):
        figure.add_trace(
            go.Scatter(
                x=sample_data["Delay Time"],
                y=sample_data["Correlation"],
                mode="lines+markers",
                name=sample_name,
                customdata=sample_data[["Replicate", "Noise Score"]],
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Delay: %{x:.3g}<br>"
                    "Correlation: %{y:.3g}<br>"
                    "Replicate: %{customdata[0]:.0f}<br>"
                    "Noise score: %{customdata[1]:.3g}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        template="plotly_white",
        height=360,
        margin={"l": 52, "r": 24, "t": 44, "b": 54},
        title={"text": "Correlogram Signal Quality", "x": 0.015, "xanchor": "left"},
        xaxis={"title": "Delay time", "type": "log", "gridcolor": "#e8eef5"},
        yaxis={"title": "Correlation", "gridcolor": "#e8eef5"},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


def render_aggregation_review(samples: list[ParsedSample]) -> None:
    flagged = [sample for sample in samples if sample_status(sample) != STATUS_NORMAL]

    if not flagged:
        st.success("No warning-level signals from the parsed metrics.")
        return

    for sample in flagged:
        sample_name = html.escape(sample.name)
        signal_text = html.escape(", ".join(sample.warnings))
        st.markdown(
            f"""
            <div class="review-card">
                <div class="review-title">{sample_name} - {sample_status(sample)}</div>
                <div class="review-signals">
                    Signals: {signal_text}<br>
                    Evidence: {html.escape(review_evidence(sample))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_small_multiples(samples: list[ParsedSample], distribution_mode: str, normalize: bool) -> None:
    columns = st.columns(3)

    for index, sample in enumerate(samples):
        diameter_column = sample.metrics["Diameter Column"]
        distribution_column = get_distribution_column(sample, distribution_mode)
        with columns[index % 3]:
            if not diameter_column or not distribution_column:
                st.info(f"{sample.name}: distribution columns not identified.")
                continue

            working = sample.data[[diameter_column, distribution_column]].dropna().sort_values(diameter_column)
            working = working[(working[diameter_column] > 0) & (working[distribution_column] >= 0)]
            if working.empty:
                st.info(f"{sample.name}: no usable distribution points.")
                continue

            y_values = working[distribution_column]
            if normalize and y_values.max() > 0:
                y_values = y_values / y_values.max() * 100

            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=working[diameter_column],
                    y=y_values,
                    mode="lines",
                    line={"width": 2.2, "color": "#2563eb"},
                    hovertemplate="Diameter: %{x:.3g} nm<br>Signal: %{y:.3g}<extra></extra>",
                )
            )
            figure.update_layout(
                template="plotly_white",
                height=220,
                margin={"l": 34, "r": 12, "t": 34, "b": 34},
                title={"text": f"{sample.name} ({sample_status(sample)})", "font": {"size": 13}},
                xaxis={"type": "log", "title": "", "showticklabels": True},
                yaxis={"title": "", "showticklabels": False},
            )
            st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


def render_raw_data(samples: list[ParsedSample], metrics: pd.DataFrame, groups=None) -> None:
    tab_results, tab_points, tab_metadata, tab_original = st.tabs(["Parsed Results", "Distribution Points", "Metadata", "Original Files"])

    with tab_results:
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        st.download_button(
            "Download parsed results",
            data=metrics.to_csv(index=False),
            file_name="labassistant_dls_results.csv",
            mime="text/csv",
        )

    with tab_points:
        selected_sample_name = st.selectbox("Sample", [sample.name for sample in samples], key="raw_points_sample")
        sample = next(item for item in samples if item.name == selected_sample_name)
        st.dataframe(sample.data, use_container_width=True, hide_index=True)
        st.download_button(
            "Download selected sample points",
            data=sample.data.to_csv(index=False),
            file_name=f"{sample.name}_distribution_points.csv",
            mime="text/csv",
        )

    with tab_metadata:
        metadata_rows = []
        for sample in samples:
            if sample.metadata:
                for key, value in sample.metadata.items():
                    metadata_rows.append({"Sample": sample.name, "Field": key, "Value": value})
            else:
                metadata_rows.append({"Sample": sample.name, "Field": "Metadata", "Value": "No metadata detected"})
        st.dataframe(pd.DataFrame(metadata_rows), use_container_width=True, hide_index=True)

    with tab_original:
        source_files = [
            {
                "label": f"{group.lot} - {classified.file_type}: {classified.file_name}",
                "name": classified.file_name,
                "type": classified.file_type,
                "text": classified.source_text or (classified.parsed_result.source_text if classified.parsed_result else ""),
                "error": classified.error,
            }
            for group in (groups or [])
            for classified in group.files
        ]
        if source_files:
            selected_file_label = st.selectbox("Original file", [item["label"] for item in source_files], key="source_text_sample")
            selected_file = next(item for item in source_files if item["label"] == selected_file_label)
            if selected_file["error"]:
                st.warning(f"{selected_file['name']}: {selected_file['error']}")
            st.caption(f"{selected_file['type']} - {selected_file['name']}")
            st.code((selected_file["text"] or "No readable source text was extracted.")[:12000], language="text")
        else:
            selected_file_name = st.selectbox("Original file", [sample.name for sample in samples], key="source_text_sample")
            sample = next(item for item in samples if item.name == selected_file_name)
            st.code(sample.source_text[:12000], language="text")


def render_empty_state() -> None:
    st.info("Upload DLS files from the sidebar to start a decision-focused batch review.")


def upload_batch_signature(uploaded_files) -> tuple[tuple[str, int | None], ...]:
    return tuple((uploaded_file.name, getattr(uploaded_file, "size", None)) for uploaded_file in uploaded_files)


def import_preview_to_session(preview, upload_signature) -> None:
    try:
        import_results = import_measurement_groups(preview.groups)
        st.session_state["imported_upload_signature"] = upload_signature
        st.session_state["imported_samples"] = [
            sample_from_measurement(result.measurement) for result in import_results if result.measurement is not None
        ]
        st.session_state["import_errors"] = [error for result in import_results for error in result.errors]
    except Exception as error:  # keep the demo alive on unexpected parser failures
        st.session_state["imported_upload_signature"] = upload_signature
        st.session_state["imported_samples"] = []
        st.session_state["import_errors"] = [f"Import failed: {error}"]


def render_import_details(preview, import_errors: list[str]) -> None:
    with st.expander("Import details", expanded=bool(import_errors)):
        st.dataframe(preview.table, use_container_width=True, hide_index=True)
        for error in import_errors:
            st.error(error)


def _completeness_mark(files) -> str:
    return f"✓ {files[0].file_name}" if files else "✗ missing"


def data_completeness_rows(groups) -> list[dict[str, str]]:
    return [
        {
            "Lot": group.lot,
            "Summary": _completeness_mark(group.summary_files),
            "Intensity distribution": _completeness_mark(group.intensity_files),
            "Correlogram": _completeness_mark(group.correlogram_files),
            "Status": group.status,
        }
        for group in groups
    ]


def render_data_completeness(groups) -> None:
    """Show which of the three export types backed each lot's analysis."""
    if not groups:
        return

    st.subheader("Data completeness")
    st.caption("Which exports were used for each lot. Summary drives Z-average/PDI, intensity drives the distribution metrics, and correlogram supports measurement confidence.")

    st.dataframe(pd.DataFrame(data_completeness_rows(groups)), use_container_width=True, hide_index=True)

    unknown_files = [classified.file_name for group in groups for classified in group.unknown_files]
    if unknown_files:
        st.caption("Unrecognized files (not used): " + ", ".join(unknown_files))


def render_history_panel(samples: list[ParsedSample] | None = None) -> None:
    records = load_history()
    with st.expander("Experiment History", expanded=False):
        if not records:
            st.info("No saved experiments yet.")
            return

        previous = latest_experiment(records)
        if samples and previous is not None:
            comparison = compare_experiments([sample.measurement for sample in samples], previous)
            drifted = comparison[comparison["Drift"].isin(["Z-average drift", "PDI drift", "Z-average drift, PDI drift"])]
            st.markdown(f"**Change vs last saved experiment** ({previous.label})")
            if drifted.empty:
                st.caption("No sample drifted beyond the Z-average or PDI thresholds since the last saved run.")
            else:
                st.caption(f"{len(drifted)} sample(s) drifted beyond threshold since the last saved run.")
            display = comparison.copy()
            for column in ["Z-Average", "Previous Z-Average", "Z Change %"]:
                display[column] = pd.to_numeric(display[column], errors="coerce").round(1)
            for column in ["PDI", "Previous PDI", "PDI Change"]:
                display[column] = pd.to_numeric(display[column], errors="coerce").round(3)
            st.dataframe(display, use_container_width=True, hide_index=True)

        summary = history_table(records)
        st.dataframe(summary, use_container_width=True, hide_index=True)

        if samples:
            st.markdown("**Find similar past runs**")
            query_name = st.selectbox("Match this sample", [sample.name for sample in samples], key="similar_query_sample")
            query_sample = next(sample for sample in samples if sample.name == query_name)
            similar = find_similar_samples(query_sample.measurement, records, top_n=5)
            if similar.empty:
                st.caption("No comparable samples in saved history yet.")
            else:
                display = similar.copy()
                display["Z-Average"] = pd.to_numeric(display["Z-Average"], errors="coerce").round(1)
                display["Primary Peak"] = pd.to_numeric(display["Primary Peak"], errors="coerce").round(1)
                display["PDI"] = pd.to_numeric(display["PDI"], errors="coerce").round(3)
                st.dataframe(display, use_container_width=True, hide_index=True)

        trends = trend_table(records).dropna(subset=["Sample"])
        if trends.empty:
            st.info("Saved experiments do not contain trendable sample metrics yet.")
            return

        metric_tabs = st.tabs(["Z-Average Trend", "PDI Trend"])
        with metric_tabs[0]:
            z_trends = trends.dropna(subset=["Z-Average"])
            if z_trends.empty:
                st.info("No saved Z-average values were found.")
            else:
                figure = go.Figure()
                for sample_name, sample_data in z_trends.groupby("Sample", sort=False):
                    figure.add_trace(
                        go.Scatter(
                            x=sample_data["Saved At"],
                            y=sample_data["Z-Average"],
                            mode="lines+markers",
                            name=sample_name,
                            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Z-Average: %{y:.3g} nm<extra></extra>",
                        )
                    )
                figure.update_layout(
                    template="plotly_white",
                    height=360,
                    margin={"l": 52, "r": 24, "t": 36, "b": 70},
                    xaxis={"title": "Saved experiment"},
                    yaxis={"title": "Z-Average (nm)", "gridcolor": "#e8eef5"},
                    legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
                )
                st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})

        with metric_tabs[1]:
            pdi_trends = trends.dropna(subset=["PDI"])
            if pdi_trends.empty:
                st.info("No saved PDI values were found.")
            else:
                figure = go.Figure()
                for sample_name, sample_data in pdi_trends.groupby("Sample", sort=False):
                    figure.add_trace(
                        go.Scatter(
                            x=sample_data["Saved At"],
                            y=sample_data["PDI"],
                            mode="lines+markers",
                            name=sample_name,
                            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>PDI: %{y:.3g}<extra></extra>",
                        )
                    )
                figure.update_layout(
                    template="plotly_white",
                    height=360,
                    margin={"l": 52, "r": 24, "t": 36, "b": 70},
                    xaxis={"title": "Saved experiment"},
                    yaxis={"title": "PDI", "gridcolor": "#e8eef5"},
                    legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
                )
                st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})


AGGREGATION_LEVEL_COLORS = {
    "None": "#2e7d32",
    "Low": "#8bc34a",
    "Moderate": "#f39c12",
    "High": "#c0392b",
    "Unknown": "#7f8c8d",
}

AGGREGATION_CATEGORY_COLORS = {
    "Low signal": "#2e7d32",
    "Watch": "#8bc34a",
    "Elevated": "#f39c12",
    "Strong signal, corroborated": "#c0392b",
    "Strong signal, repeat recommended": "#e67e22",
    "Unavailable": "#7f8c8d",
}

CHECK_ICONS = {"supports": "✅", "neutral": "➖", "insufficient": "❔"}


def render_aggregation_detection(samples: list[ParsedSample]) -> None:
    """Prominent dual-angle protein-aggregation detection panel.

    Renders only when at least one sample has a forward + backscatter angle pair.
    """
    assessments = [(sample, assess_dual_angle_aggregation(sample.measurement)) for sample in samples]
    available = [(sample, assessment) for sample, assessment in assessments if assessment.available]
    if not available:
        return

    st.subheader("Dual-Angle Aggregation Detection")
    st.caption(
        "Forward scatter (~12.8°) is far more sensitive to large species than backscatter "
        "(~173°). Aggregation Index = Z-average(forward) / Z-average(backscatter) − 1. Near 0 "
        "the angles agree; an elevated index points to forward-angle large-species enrichment — a "
        "screening signal that requires corroboration, not proof of aggregation. The corroboration "
        "checklist below shows the supporting evidence. Reference baseline (Malvern "
        "AN101104/AN140527): ~0.05 stable, ~0.1 at aggregation onset."
    )

    cards = st.columns(len(available))
    for column, (sample, assessment) in zip(cards, available):
        color = AGGREGATION_CATEGORY_COLORS.get(assessment.category, "#7f8c8d")
        with column:
            st.markdown(
                f"""
                <div style="border:1px solid #e2e8f0;border-left:6px solid {color};border-radius:10px;padding:14px 16px;">
                    <div style="font-size:0.85rem;color:#475569;">{html.escape(sample.name)}</div>
                    <div style="font-size:2.0rem;font-weight:700;color:{color};line-height:1.2;">{assessment.aggregation_index:.2f}</div>
                    <div style="font-size:0.9rem;font-weight:600;color:{color};">{html.escape(assessment.category)}</div>
                    <div style="font-size:0.8rem;color:#64748b;margin-top:6px;">Corroboration {assessment.corroboration_score}/{assessment.corroboration_max}<br>Confidence: {assessment.confidence}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(_forward_back_z_chart(available), use_container_width=True, config={"displaylogo": False})
    with chart_cols[1]:
        st.plotly_chart(_aggregation_index_chart(available), use_container_width=True, config={"displaylogo": False})

    st.markdown("**Paired intensity distribution by angle**")
    overlay_name = st.selectbox("Sample", [sample.name for sample, _ in available], key="aggregation_overlay_sample")
    overlay_sample = next(sample for sample, _ in available if sample.name == overlay_name)
    paired = _paired_angle_overlay(overlay_sample)
    if paired is None:
        st.caption("Per-angle distribution curves are not available for this sample.")
    else:
        st.plotly_chart(paired, use_container_width=True, config={"displaylogo": False})

    st.markdown("**Corroboration checklist** — why the interpretation was assigned")
    checklist_name = st.selectbox("Sample", [sample.name for sample, _ in available], key="aggregation_checklist_sample")
    _, checklist_assessment = next((sample, assessment) for sample, assessment in available if sample.name == checklist_name)
    color = AGGREGATION_CATEGORY_COLORS.get(checklist_assessment.category, "#7f8c8d")
    st.markdown(
        f"<div style='font-size:1.05rem;font-weight:700;color:{color};'>{html.escape(checklist_assessment.category)} "
        f"· corroboration {checklist_assessment.corroboration_score}/{checklist_assessment.corroboration_max}</div>"
        f"<div style='color:#334155;margin:4px 0 8px;'>{html.escape(checklist_assessment.headline)}</div>",
        unsafe_allow_html=True,
    )
    for check in checklist_assessment.checks:
        icon = CHECK_ICONS.get(check.status, "•")
        st.markdown(f"{icon} **{check.label}** — {check.detail}")
    st.info(checklist_assessment.recommendation)
    st.caption(checklist_assessment.summary)

    with st.expander("All samples: interpretation summary", expanded=False):
        for sample, assessment in available:
            st.markdown(
                f"**{sample.name}** — {assessment.category} "
                f"(index {assessment.aggregation_index:.2f}, corroboration {assessment.corroboration_score}/{assessment.corroboration_max})"
            )
            st.caption(assessment.recommendation)


def _forward_back_z_chart(available) -> go.Figure:
    names = [sample.name for sample, _ in available]
    forward_values = [assessment.forward.z_average for _, assessment in available]
    backward_values = [assessment.backward.z_average for _, assessment in available]
    figure = go.Figure()
    figure.add_trace(go.Bar(x=names, y=forward_values, name="Forward ~12.8°", marker_color="#2c7fb8", hovertemplate="<b>%{x}</b><br>Forward: %{y:.3g} nm<extra></extra>"))
    figure.add_trace(go.Bar(x=names, y=backward_values, name="Backscatter ~173°", marker_color="#d95f0e", hovertemplate="<b>%{x}</b><br>Backscatter: %{y:.3g} nm<extra></extra>"))
    figure.update_layout(
        template="plotly_white",
        barmode="group",
        height=320,
        title="Forward vs backscatter Z-average",
        margin={"l": 52, "r": 24, "t": 48, "b": 60},
        yaxis={"title": "Z-Average (nm)", "gridcolor": "#e8eef5"},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    return figure


def _aggregation_index_chart(available) -> go.Figure:
    names = [sample.name for sample, _ in available]
    indices = [assessment.aggregation_index for _, assessment in available]
    colors = [AGGREGATION_LEVEL_COLORS.get(assessment.level, "#7f8c8d") for _, assessment in available]
    figure = go.Figure()
    figure.add_trace(go.Bar(x=names, y=indices, marker_color=colors, hovertemplate="<b>%{x}</b><br>Aggregation Index: %{y:.3g}<extra></extra>"))
    figure.add_hline(y=INDEX_ELEVATED, line_dash="dash", line_color="#c0392b", annotation_text="elevated (0.10)", annotation_position="top left")
    figure.add_hline(y=INDEX_WATCH, line_dash="dot", line_color="#f39c12", annotation_text="watch (0.05)", annotation_position="bottom left")
    figure.update_layout(
        template="plotly_white",
        height=320,
        title="Aggregation Index by sample",
        margin={"l": 52, "r": 24, "t": 48, "b": 60},
        yaxis={"title": "Aggregation Index", "gridcolor": "#e8eef5"},
    )
    return figure


def _paired_angle_overlay(sample: ParsedSample) -> go.Figure | None:
    distributions = sample.measurement.distributions
    forward = distributions.get("angle_forward")
    backward = distributions.get("angle_back")
    if not forward or not forward.diameter_nm or not backward or not backward.diameter_nm:
        return None

    figure = go.Figure()
    for distribution, name, color in [(forward, "Forward ~12.8°", "#2c7fb8"), (backward, "Backscatter ~173°", "#d95f0e")]:
        figure.add_trace(
            go.Scatter(
                x=distribution.diameter_nm,
                y=distribution.intensity,
                mode="lines",
                name=name,
                line={"color": color, "width": 2},
                hovertemplate="<b>" + name + "</b><br>%{x:.3g} nm<br>%{y:.3g}%<extra></extra>",
            )
        )
    figure.update_layout(
        template="plotly_white",
        height=340,
        title=f"{sample.name}: intensity distribution by angle",
        margin={"l": 52, "r": 24, "t": 48, "b": 52},
        xaxis={"title": "Diameter (nm)", "type": "log", "gridcolor": "#e8eef5"},
        yaxis={"title": "Intensity (%)", "gridcolor": "#e8eef5"},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    return figure


def render_angle_breakdown(samples: list[ParsedSample]) -> None:
    """Per-angle detail table for dual-angle runs (secondary diagnostic).

    The forward vs backscatter comparison and paired overlay live in the
    Dual-Angle Aggregation Detection panel; this is the full per-angle table with
    counts, replicates, PDI, and per-angle peak/D50. Renders only when a
    dual-angle run is present.
    """
    angle_table = build_angle_table(samples)
    if angle_table.empty:
        return

    st.markdown("**Per-angle detail**")
    st.caption("Forward (~12.8°) and backscatter (~173°) values for each lot, from the summary and per-angle distributions.")
    display = angle_table.copy()
    for column in ["Z-Average", "PDI", "Max Z-Average", "Primary Peak", "D50"]:
        display[column] = pd.to_numeric(display[column], errors="coerce").round(3 if column == "PDI" else 1)
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_primary_visualization(
    samples: list[ParsedSample],
    distribution_mode: str,
    normalize: bool,
    show_peaks: bool,
) -> None:
    st.subheader("Primary Distribution Review")
    control_cols = st.columns([2, 2, 1, 1])
    with control_cols[0]:
        selected_names = st.multiselect(
            "Visible samples",
            [sample.name for sample in samples],
            default=[sample.name for sample in samples[: min(len(samples), 8)]],
        )
    with control_cols[1]:
        reference_name = st.selectbox("Reference sample", ["None"] + [sample.name for sample in samples])
    with control_cols[2]:
        view_mode = st.radio("View", ["Overlay", "Delta"], horizontal=True)
    with control_cols[3]:
        if st.button("Show flagged only", use_container_width=True):
            selected_names = [sample.name for sample in samples if sample_status(sample) != STATUS_NORMAL]

    if not selected_names:
        st.info("Select at least one sample to display the distribution overlay.")
    elif view_mode == "Delta":
        render_difference_chart(samples, selected_names, distribution_mode, reference_name)
    else:
        render_distribution_chart(samples, selected_names, distribution_mode, normalize, show_peaks, reference_name)


def main() -> None:
    add_page_style()

    st.title("LabAssistant")
    st.caption("DLS batch comparison and aggregation review")

    with st.sidebar:
        st.header("Data")
        uploaded_files = st.file_uploader("Upload DLS files", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

    if not uploaded_files:
        st.session_state.pop("imported_upload_signature", None)
        st.session_state.pop("imported_samples", None)
        st.session_state.pop("import_errors", None)
        render_empty_state()
        return

    upload_signature = upload_batch_signature(uploaded_files)
    if st.session_state.get("imported_upload_signature") != upload_signature:
        st.session_state.pop("imported_samples", None)
        st.session_state.pop("import_errors", None)

    preview = build_import_preview(uploaded_files)
    if st.session_state.get("imported_upload_signature") != upload_signature:
        import_preview_to_session(preview, upload_signature)

    has_imported_samples = bool(st.session_state.get("imported_samples"))
    with st.sidebar:
        st.divider()
        st.header("Import")
        st.dataframe(preview.table, use_container_width=True, hide_index=True)
        import_label = "Re-import grouped measurements" if has_imported_samples else "Retry grouped import"
        if st.button(import_label, use_container_width=True):
            import_preview_to_session(preview, upload_signature)
        st.divider()
        st.header("Distribution")
        cached_samples = st.session_state.get("imported_samples", [])
        signal_options = available_signals(cached_samples) if cached_samples else ["Intensity"]
        distribution_mode = st.radio("Signal", signal_options, horizontal=True)
        if len(signal_options) == 1:
            st.caption(f"Only {signal_options[0].lower()} distribution data is available in this batch.")
        normalize = st.checkbox("Normalize curves", value=True)
        show_peaks = st.checkbox("Show peaks", value=True)

    samples = st.session_state.get("imported_samples", [])
    import_errors = st.session_state.get("import_errors", [])

    if not samples:
        st.info("Import the detected measurement groups from the sidebar to begin review.")
        if import_errors:
            st.warning("The last import did not produce any usable measurements:")
            for error in import_errors:
                st.error(error)
        return

    with st.sidebar:
        st.divider()
        st.header("History")
        history_label = st.text_input("Experiment label", value="")
        if st.button("Save current experiment", use_container_width=True):
            record = save_experiment([sample.measurement for sample in samples], history_label)
            st.success(f"Saved {record.label}")
        st.divider()
        st.header("Report")
        st.button("Export report", use_container_width=True, disabled=True, help="Report export is coming in a future version.")
        st.caption("Report export is coming soon.")

    metrics = build_metrics_table(samples)

    render_decision_workbench(samples, metrics)
    render_data_completeness(preview.groups)
    render_aggregation_detection(samples)
    render_import_details(preview, import_errors)
    render_history_panel(samples)

    render_primary_visualization(samples, distribution_mode, normalize, show_peaks)

    st.subheader("Key Metric Comparison")
    comparison_cols = st.columns(2)
    with comparison_cols[0]:
        render_metric_dot_plot(metrics, "Z-Average", "Z-Average", "nm")
    with comparison_cols[1]:
        render_metric_dot_plot(metrics, "PDI", "PDI", threshold=0.30)

    st.subheader("Sample Summary")
    card_columns = st.columns(min(4, len(samples)))
    for index, sample in enumerate(samples):
        with card_columns[index % len(card_columns)]:
            render_sample_card(sample)

    with st.expander("Secondary charts and diagnostics"):
        render_angle_breakdown(samples)

        render_data_analysis(samples, metrics)

        comparison_cols = st.columns(2)
        with comparison_cols[0]:
            render_peak_plot(metrics)
        with comparison_cols[1]:
            render_distribution_spread_plot(metrics)

        comparison_cols = st.columns(2)
        with comparison_cols[0]:
            render_metric_dot_plot(metrics, "Tail Index", "Large-Particle Tail Index", "%", threshold=5)
        with comparison_cols[1]:
            render_signal_matrix(metrics)

        render_correlogram_quality_chart(samples)

    with st.expander("Small multiples", expanded=False):
        render_small_multiples(samples, distribution_mode, normalize)

    with st.expander("Raw data and metadata"):
        render_raw_data(samples, metrics, preview.groups)


if __name__ == "__main__":
    main()
