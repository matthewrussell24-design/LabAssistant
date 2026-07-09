from __future__ import annotations

import html
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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
from labassistant.importers.chromatography import (
    assess_chromatography_mass_balance,
    chromatography_observations,
    parse_chromatography_csv,
    peak_area_trend_table,
    total_area_trend_table,
)
from labassistant.importers.filtration import FiltrationImportResult, parse_filtration_csv
from labassistant.importers.openlab_olax import build_experiment_from_olax
from labassistant.history import (
    compare_experiments,
    find_similar_samples,
    history_table,
    latest_experiment,
    load_history,
    measurements_from_record,
    save_experiment,
    trend_table,
)
from labassistant.metrics import (
    find_local_peaks,
)
from labassistant.chromatography import mass_balance_hypotheses
from labassistant.context_engine import ContextRetriever, KnowledgeStore, ResearchJournal
from labassistant.filtration import (
    FILTRATION_DIFFICULTY_RUBRIC,
    PRESSURE_UNIT_LABELS,
    PRESSURE_UNITS_TO_KPA,
    filtration_measurement_to_table_row,
    normalize_pressure,
    validate_difficulty_score,
)
from labassistant.models import Experiment, FiltrationMeasurement
from labassistant.observations import (
    build_experiment_brief_from_observations,
    observation_table,
    observations_from_samples,
)
from labassistant.trend_analysis import (
    CIRCULATION_TIME_UNITS_TO_MINUTES,
    ForwardScatterPoint,
    FiltrationTrendPoint,
    RelationshipAnalysis,
    apply_circulation_time,
    apply_filtration_measurement,
    build_data_story,
    build_filtration_trend_analysis,
    build_forward_scatter_trend_analysis_from_measurements,
    circulation_time_from_measurement,
    control_chart_table,
    filtration_measurement_from_provenance,
    replicate_statistics_table,
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


CHROMATOGRAPHY_FIXTURE_PATH = Path("sample_data/chromatography/mass_balance_demo.csv")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def render_data_story(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    story = build_data_story(samples, metrics)

    st.subheader("Data Story")
    st.caption("Trend-aware summary of stability, variability, and signals worth checking first.")

    story_columns = st.columns(3)
    for column, (title, items) in zip(story_columns, story.items()):
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


def render_experiment_brief(samples: list[ParsedSample]) -> None:
    observations = observations_from_samples(samples)
    brief = build_experiment_brief_from_observations(observations, sample_count=len(samples))

    st.subheader("Experiment Brief")
    st.caption("Generated from normalized observations derived from the current DLS measurements.")

    columns = st.columns(4)
    for column, (question, answers) in zip(columns, brief.items()):
        with column:
            st.markdown(
                f"""
                <div class="summary-card">
                    <div class="summary-title">{html.escape(question)}</div>
                    <ul>
                        {''.join(f'<li>{html.escape(answer)}</li>' for answer in answers)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Observations", expanded=any(observation.severity in {"review", "watch"} for observation in observations)):
        table = observation_table(observations)
        if table.empty:
            st.info("No observations generated yet.")
        else:
            display_columns = ["sample_name", "label", "category", "severity", "confidence", "evidence", "recommendation"]
            display = table[[column for column in display_columns if column in table.columns]].rename(
                columns={
                    "sample_name": "Sample",
                    "label": "Observation",
                    "category": "Category",
                    "severity": "Severity",
                    "confidence": "Confidence",
                    "evidence": "Evidence",
                    "recommendation": "Recommended Next Check",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


def dls_experiment_from_samples(
    samples: list[ParsedSample],
    *,
    label: str = "",
    source_files: list[str] | None = None,
) -> Experiment:
    observations = observations_from_samples(samples)
    experiment_label = label.strip() or "DLS experiment"
    metadata = {
        "sample_count": len(samples),
        "source_files": list(source_files or []),
    }
    return Experiment(
        experiment_id=uuid4().hex,
        label=experiment_label,
        instrument="DLS",
        technique="DLS",
        source_path=None,
        created_at=_utc_now(),
        measurements=[sample.measurement for sample in samples],
        observations=observations,
        metadata=metadata,
    )


def chromatography_experiment_from_preview(
    preview: dict,
    *,
    label: str = "",
    source_name: str | None = None,
) -> Experiment:
    if "openlab_experiment" in preview:
        experiment = preview["openlab_experiment"]
        if label.strip():
            experiment.label = label.strip()
        if source_name:
            experiment.source_path = source_name
            experiment.metadata["source_name"] = source_name
        return experiment

    observations = list(preview.get("observations") or [])
    hypotheses = list(preview.get("hypotheses") or [])
    assessment = preview.get("assessment")
    experiment_label = label.strip() or "Chromatography experiment"
    unsupported_sections = []
    if not any(observation.label == "Peak table available" for observation in observations):
        unsupported_sections.append("Chromatography CSV import does not include raw detector signal traces.")
    return Experiment(
        experiment_id=uuid4().hex,
        label=experiment_label,
        instrument="Chromatography",
        technique="HPLC",
        source_path=source_name,
        created_at=_utc_now(),
        measurements=list(preview.get("measurements") or []),
        observations=observations,
        unsupported_sections=unsupported_sections,
        metadata={
            "source_name": source_name,
            "hypotheses": hypotheses,
            "assessment": assessment.to_dict() if hasattr(assessment, "to_dict") else {},
        },
    )


def save_experiment_to_memory(
    experiment: Experiment,
    *,
    human_note: str = "",
    project_id: str | None = None,
    tags: list[str] | None = None,
) -> None:
    store = KnowledgeStore()
    store.add_experiment(experiment, project_id=project_id, tags=tags or [])
    for hypothesis in experiment.metadata.get("hypotheses", []):
        store.add_hypothesis(
            str(hypothesis),
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "hypothesis"],
        )
    for recommendation in experiment.metadata.get("recommendations", []):
        store.add_recommendation(
            str(recommendation),
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "recommendation"],
        )
    if human_note.strip():
        store.add_note(
            human_note.strip(),
            title=f"Note: {experiment.label}",
            experiment_id=experiment.experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            tags=[experiment.technique or "", "human_note"],
        )


def _packet_items_table(items) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Title": item.title,
                "Layer": item.layer,
                "Type": item.entity_type,
                "Confidence": item.confidence,
                "Text": item.text,
            }
            for item in items
        ]
    )


def render_context_packet(packet) -> None:
    st.markdown(f"**Confidence:** {packet.confidence}")
    if packet.caveats:
        for caveat in packet.caveats:
            st.caption(caveat)

    sections = [
        ("Relevant experiments", packet.relevant_experiments),
        ("Relevant observations", packet.relevant_observations),
        ("Supporting evidence", packet.supporting_evidence),
        ("Related notes", packet.related_notes),
        ("Source files", packet.source_files),
    ]
    for title, items in sections:
        st.markdown(f"**{title}**")
        table = _packet_items_table(items)
        if table.empty:
            st.caption("No matching items.")
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

    if packet.hypotheses:
        st.markdown("**Hypotheses**")
        for item in packet.hypotheses:
            st.markdown(f"- {item.text}")
    if packet.recommendations:
        st.markdown("**Recommendations**")
        for item in packet.recommendations:
            st.markdown(f"- {item.text}")
    if packet.missing_information:
        st.markdown("**Missing information**")
        for item in packet.missing_information:
            st.warning(item)


def render_memory_panel(
    *,
    dls_experiment: Experiment | None = None,
    chromatography_experiment: Experiment | None = None,
) -> None:
    available = []
    if dls_experiment is not None:
        available.append(("DLS", dls_experiment))
    if chromatography_experiment is not None:
        available.append(("Chromatography", chromatography_experiment))

    with st.expander("LabAssistant Memory", expanded=False):
        st.caption("Save selected outputs to local memory, then retrieve compact context. No LLM or chat is used.")
        if available:
            labels = [label for label, _ in available]
            selected_label = st.selectbox("Experiment to save", labels, key="memory_experiment_choice")
            selected_experiment = next(experiment for label, experiment in available if label == selected_label)
            memory_label = st.text_input(
                "Memory label",
                value=selected_experiment.label,
                key="memory_label",
            )
            project_id = st.text_input("Project tag", value="", key="memory_project")
            human_note = st.text_area("Human notes", value="", key="memory_human_note")
            if st.button("Save to LabAssistant Memory", use_container_width=True):
                selected_experiment.label = memory_label.strip() or selected_experiment.label
                save_experiment_to_memory(
                    selected_experiment,
                    human_note=human_note,
                    project_id=project_id.strip() or None,
                    tags=[selected_label, selected_experiment.technique or ""],
                )
                st.success(f"Saved {selected_experiment.label} to local LabAssistant Memory.")
        else:
            st.info("Import DLS or chromatography data before saving to memory.")

        st.divider()
        st.markdown("**Ask memory / Retrieve context**")
        question = st.text_input("Keyword question", value="", key="memory_question")
        if st.button("Retrieve context", use_container_width=True):
            if question.strip():
                packet = ContextRetriever(KnowledgeStore()).retrieve(question)
                st.session_state["memory_context_packet"] = packet
            else:
                st.warning("Enter a keyword question before retrieving context.")
        packet = st.session_state.get("memory_context_packet")
        if packet is not None:
            render_context_packet(packet)


def _journal_entries_table(entries) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date/time": entry.created_at,
                "Experiment": entry.title,
                "Instrument": entry.instrument,
                "Tags": ", ".join(entry.tags),
                "Samples": ", ".join(entry.samples),
                "Observations": "\n".join(entry.key_observations[:4]),
                "Hypotheses": "\n".join(entry.hypotheses[:3]),
                "Recommendations": "\n".join(entry.recommendations[:3]),
                "Source files": ", ".join(entry.source_files),
                "Notes": "\n".join(entry.notes[:3]),
            }
            for entry in entries
        ]
    )


def render_research_journal_panel() -> None:
    with st.expander("Research Journal", expanded=False):
        st.caption("A local journal view over saved experiments and manual notes. No LLM generation is used.")
        store = KnowledgeStore()
        journal = ResearchJournal(store)

        st.markdown("**Standalone journal note**")
        note_cols = st.columns([1, 1, 1])
        note_title = note_cols[0].text_input("Note title", value="", key="journal_note_title")
        note_tags = note_cols[1].text_input("Tags", value="", key="journal_note_tags", help="Comma-separated")
        note_instrument = note_cols[2].text_input("Instrument", value="", key="journal_note_instrument")
        note_text = st.text_area("Note text", value="", key="journal_note_text")
        if st.button("Add journal note", use_container_width=True):
            if note_text.strip():
                store.add_note(
                    note_text.strip(),
                    title=note_title.strip() or "Research note",
                    instrument_id=note_instrument.strip() or None,
                    tags=[tag.strip() for tag in note_tags.split(",") if tag.strip()],
                )
                st.success("Journal note added.")
            else:
                st.warning("Write a note before adding it to the journal.")

        st.divider()
        st.markdown("**Search / filter**")
        filter_cols = st.columns(4)
        keyword = filter_cols[0].text_input("Keyword", value="", key="journal_filter_keyword")
        tag = filter_cols[1].text_input("Tag", value="", key="journal_filter_tag")
        instrument = filter_cols[2].text_input("Instrument", value="", key="journal_filter_instrument")
        sample = filter_cols[3].text_input("Sample", value="", key="journal_filter_sample")

        entries = journal.entries(keyword=keyword, tag=tag, instrument=instrument, sample=sample)
        if not entries:
            st.info("No research journal entries matched the current filters.")
        else:
            st.dataframe(_journal_entries_table(entries), use_container_width=True, hide_index=True)

        markdown = journal.export_markdown(keyword=keyword, tag=tag, instrument=instrument, sample=sample)
        st.download_button(
            "Export journal to Markdown",
            data=markdown,
            file_name="labassistant_research_journal.md",
            mime="text/markdown",
            use_container_width=True,
        )


def render_decision_workbench(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    render_experiment_brief(samples)
    render_health_strip(samples, metrics)
    render_decision_brief(samples, metrics)
    render_data_story(samples, metrics)

    finding_col, review_col = st.columns([1.45, 1])
    with finding_col:
        render_control_charts(samples, metrics)
    with review_col:
        st.subheader("Samples To Inspect")
        render_aggregation_review(samples)


def load_chromatography_preview(source) -> dict:
    source_name = getattr(source, "name", None) or str(source)
    if source_name.lower().endswith(".olax"):
        return load_openlab_olax_preview(source, source_name=source_name)

    measurements = parse_chromatography_csv(source)
    assessment = assess_chromatography_mass_balance(measurements)
    observations = chromatography_observations(measurements, assessment)
    hypotheses = mass_balance_hypotheses(observations)
    return {
        "measurements": measurements,
        "assessment": assessment,
        "observations": observations,
        "hypotheses": hypotheses,
        "source_name": source_name,
        "peak_area_trend": peak_area_trend_table(measurements),
        "total_area_trend": total_area_trend_table(measurements),
    }


def load_openlab_olax_preview(source, *, source_name: str) -> dict:
    if isinstance(source, (str, Path)):
        experiment = build_experiment_from_olax(source, label=Path(source_name).name)
    else:
        source.seek(0)
        data = source.read()
        with tempfile.NamedTemporaryFile(suffix=".olax") as temporary:
            temporary.write(data)
            temporary.flush()
            experiment = build_experiment_from_olax(temporary.name, label=Path(source_name).name)
    experiment.source_path = source_name
    experiment.metadata["source_name"] = source_name
    return {
        "openlab_experiment": experiment,
        "measurements": experiment.measurements,
        "observations": experiment.observations,
        "hypotheses": [],
        "source_name": source_name,
    }


def render_chromatography_preview(preview: dict) -> None:
    if "openlab_experiment" in preview:
        render_openlab_preview(preview["openlab_experiment"])
        return

    assessment = preview["assessment"]
    observations = preview["observations"]
    hypotheses = preview["hypotheses"]

    st.subheader("Chromatography / Mass Balance Preview")
    st.caption("Proof of concept: simple CSV to chromatography measurements, observations, and mass-balance hypotheses.")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Parent Area", format_metric(assessment.parent_area_percent, "%"))
    metric_cols[1].metric("Known Impurity", format_metric(assessment.known_impurity_area_percent, "%"))
    metric_cols[2].metric("Unknown Area", format_metric(assessment.unknown_area_percent, "%"))
    metric_cols[3].metric("Total Area Change", format_metric(assessment.total_area_change_percent, "%"))
    metric_cols[4].metric("Replicate RSD", format_metric(assessment.replicate_rsd_percent, "%"))

    trend_cols = st.columns([1.3, 1])
    with trend_cols[0]:
        st.markdown("**Peak area trend**")
        peak_trend = preview["peak_area_trend"].copy()
        for column in peak_trend.columns:
            if column != "Timepoint":
                peak_trend[column] = pd.to_numeric(peak_trend[column], errors="coerce").round(2)
        st.dataframe(peak_trend, use_container_width=True, hide_index=True)
    with trend_cols[1]:
        st.markdown("**Total area trend**")
        total_trend = preview["total_area_trend"].copy()
        for column in ["Total Area", "Change vs Start %"]:
            total_trend[column] = pd.to_numeric(total_trend[column], errors="coerce").round(2)
        st.dataframe(total_trend, use_container_width=True, hide_index=True)

    obs_cols = st.columns([1.4, 1])
    with obs_cols[0]:
        st.markdown("**Generated observations**")
        table = observation_table(observations)
        if table.empty:
            st.info("No chromatography observations generated.")
        else:
            display_columns = ["sample_name", "label", "category", "severity", "evidence", "recommendation"]
            display = table[[column for column in display_columns if column in table.columns]].rename(
                columns={
                    "sample_name": "Sample",
                    "label": "Observation",
                    "category": "Category",
                    "severity": "Severity",
                    "evidence": "Evidence",
                    "recommendation": "Recommended Next Check",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
    with obs_cols[1]:
        st.markdown("**Possible hypotheses**")
        if hypotheses:
            for hypothesis in hypotheses:
                st.markdown(f"- {hypothesis}")
        else:
            st.info("No mass-balance hypotheses generated.")


def render_openlab_preview(experiment: Experiment) -> None:
    observations = list(experiment.observations)
    metadata = experiment.metadata

    st.subheader("OpenLab (.olax) Preview")
    st.caption("Agilent OpenLab archive import: sequence, injections, detector packages, methods, and structured observations.")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Injections", len(experiment.measurements))
    metric_cols[1].metric("Detector files", len(metadata.get("detector_files", [])))
    metric_cols[2].metric("Peak tables", len(metadata.get("peak_table_files", [])))
    metric_cols[3].metric("Methods", len(metadata.get("acquisition_method_files", [])))
    metric_cols[4].metric("Audit files", len(metadata.get("audit_files", [])))

    rows = []
    for measurement in experiment.measurements:
        rows.append(
            {
                "Injection": measurement.injection_id,
                "Sample": measurement.sample_name,
                "Method": measurement.method_name,
                "Signal files": len(measurement.metadata.get("openlab_signal_files", [])),
                "Peaks parsed": len(measurement.peaks),
                "Raw data file": measurement.metadata.get("raw_data_file"),
                "Acquired": measurement.metadata.get("measurement_datetime"),
            }
        )
    st.markdown("**Injections**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    obs_cols = st.columns([1.35, 1])
    with obs_cols[0]:
        st.markdown("**Generated observations**")
        table = observation_table(observations)
        if table.empty:
            st.info("No OpenLab observations generated.")
        else:
            display_columns = ["sample_name", "label", "category", "severity", "confidence", "evidence", "recommendation"]
            display = table[[column for column in display_columns if column in table.columns]].rename(
                columns={
                    "sample_name": "Sample",
                    "label": "Observation",
                    "category": "Category",
                    "severity": "Severity",
                    "confidence": "Confidence",
                    "evidence": "Evidence",
                    "recommendation": "Recommended Next Check",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
    with obs_cols[1]:
        st.markdown("**Import limitations**")
        if experiment.unsupported_sections:
            st.caption("The OLAX archive was imported successfully, but some internal data sections are not yet decoded.")
            for section in experiment.unsupported_sections:
                st.warning(section)
        else:
            st.caption("The OLAX archive was imported successfully and no import limitations were reported.")
        if not metadata.get("peak_table_files"):
            st.caption("No peak/result table was detected, so quantitative peak interpretation is limited.")


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


def render_control_charts(samples: list[ParsedSample], metrics: pd.DataFrame) -> None:
    chart_data = control_chart_table(samples, metrics)
    st.subheader("Control Chart Signals")
    if chart_data.empty:
        st.info("At least two parsed values are needed to calculate warning and action limits.")
        return

    metric_options = chart_data["Metric"].drop_duplicates().tolist()
    selected_metric = st.selectbox("Metric", metric_options, key="control_chart_metric")
    working = chart_data[chart_data["Metric"] == selected_metric]
    colors = working["Zone"].map({"In control": "#047857", "Warning": "#b45309", "Action": "#b91c1c"}).fillna("#2563eb")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=working["Sample"],
            y=working["Value"],
            mode="lines+markers",
            marker={"size": 11, "color": colors},
            line={"color": "#64748b", "width": 1.8},
            text=working["Zone"],
            hovertemplate="<b>%{x}</b><br>Value: %{y:.3g}<br>%{text}<extra></extra>",
        )
    )
    first = working.iloc[0]
    figure.add_hline(y=first["Mean"], line_color="#0f172a", line_width=1, annotation_text="mean")
    figure.add_hline(y=first["Warning High"], line_dash="dot", line_color="#b45309", annotation_text="+2 SD")
    figure.add_hline(y=first["Warning Low"], line_dash="dot", line_color="#b45309", annotation_text="-2 SD")
    figure.add_hline(y=first["Action High"], line_dash="dash", line_color="#b91c1c", annotation_text="+3 SD")
    figure.add_hline(y=first["Action Low"], line_dash="dash", line_color="#b91c1c", annotation_text="-3 SD")
    figure.update_layout(
        template="plotly_white",
        height=330,
        margin={"l": 52, "r": 24, "t": 36, "b": 62},
        xaxis={"title": "Imported order"},
        yaxis={"title": selected_metric, "gridcolor": "#e8eef5"},
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


def render_saved_experiment_loader() -> None:
    records = load_history()
    compatible_records = [record for record in records if record.measurements]
    if not compatible_records:
        return
    st.subheader("Load Saved DLS Experiment")
    st.caption("History is append-only. Loading a saved experiment restores editable UI state; saving again creates a new saved version.")
    labels = [
        f"{record.saved_at} · {record.label} · {len(record.measurements)} sample(s) · {record.id[:8]}"
        for record in compatible_records
    ]
    selected_label = st.selectbox("Saved experiment", labels, key="saved_experiment_to_load")
    selected_record = compatible_records[labels.index(selected_label)]
    if st.button("Load saved experiment into workspace", use_container_width=True):
        measurements = measurements_from_record(selected_record)
        st.session_state["imported_upload_signature"] = ("history", selected_record.id)
        st.session_state["imported_samples"] = [sample_from_measurement(measurement) for measurement in measurements]
        st.session_state["import_errors"] = []
        st.session_state["loaded_history_record"] = selected_record.to_dict()
        st.session_state["history_label"] = f"{selected_record.label} (updated)"
        st.rerun()


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

        render_saved_experiment_loader()
        st.divider()

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


def apply_session_experimental_variables(samples: list[ParsedSample]) -> None:
    for sample in samples:
        time_value = parse_optional_float(st.session_state.get(f"circulation_time::{sample.name}"))
        time_unit = st.session_state.get(f"circulation_time_unit::{sample.name}")
        if time_value is not None and time_unit in CIRCULATION_TIME_UNITS_TO_MINUTES:
            apply_circulation_time(sample.measurement, time_value, str(time_unit))

        ordinal_score = parse_filtration_score(st.session_state.get(f"filtration_difficulty::{sample.name}"))
        if ordinal_score is None:
            continue
        filtration_time = parse_optional_float(st.session_state.get(f"filtration_time::{sample.name}"))
        pressure = parse_optional_float(st.session_state.get(f"filtration_pressure::{sample.name}"))
        pressure_unit = st.session_state.get(f"filtration_pressure_unit::{sample.name}")
        pressure_kpa = normalize_pressure(pressure, pressure_unit) if pressure is not None and pressure_unit in PRESSURE_UNITS_TO_KPA else None
        clogging_value = st.session_state.get(f"filtration_clogging::{sample.name}", "Not recorded")
        clogging_observed = {"Yes": True, "No": False}.get(str(clogging_value))
        apply_filtration_measurement(
            sample.measurement,
            FiltrationMeasurement(
                sample_name=sample.name,
                difficulty_score=float(ordinal_score),
                filtration_time_minutes=filtration_time,
                pressure=pressure,
                pressure_unit=str(pressure_unit) if pressure_unit in PRESSURE_UNITS_TO_KPA else None,
                pressure_kpa=pressure_kpa,
                filter_type=(st.session_state.get(f"filtration_filter::{sample.name}") or "").strip() or None,
                clogging_observed=clogging_observed,
                notes=(st.session_state.get(f"filtration_notes::{sample.name}") or "").strip() or None,
            ),
        )


def render_forward_scatter_trend_explorer(samples: list[ParsedSample]) -> None:
    st.subheader("Forward-Scatter Trend Explorer")
    st.caption(
        "Enter total circulation time explicitly for each imported DLS sample. "
        "LabAssistant uses the current sample names as mapping keys, normalizes time to minutes for statistics, and does not infer experimental variables from lot numbers or import order."
    )

    input_columns = st.columns(min(3, len(samples)))
    invalid_time_samples: list[str] = []
    for index, sample in enumerate(samples):
        existing_time = circulation_time_from_measurement(sample.measurement)
        time_key = f"circulation_time::{sample.name}"
        unit_key = f"circulation_time_unit::{sample.name}"
        if existing_time and time_key not in st.session_state:
            st.session_state[time_key] = str(existing_time["value"])
        if existing_time and unit_key not in st.session_state:
            st.session_state[unit_key] = str(existing_time["unit"])

        with input_columns[index % len(input_columns)]:
            raw_value = st.text_input(
                sample.name,
                key=time_key,
                placeholder="e.g. 45",
                help="Total circulation time for this sample. Leave blank if it was not measured.",
            )
            st.selectbox(
                "Unit",
                list(CIRCULATION_TIME_UNITS_TO_MINUTES),
                key=unit_key,
                help="Time is stored with this unit and normalized to minutes for charts and correlation.",
            )
        parsed_value = parse_optional_float(raw_value)
        if parsed_value is None and str(raw_value).strip():
            invalid_time_samples.append(sample.name)

    if invalid_time_samples:
        st.warning("Enter numeric circulation times for: " + ", ".join(invalid_time_samples))

    apply_session_experimental_variables(samples)
    analysis = build_forward_scatter_trend_analysis_from_measurements(samples)
    if not analysis.points:
        st.info("Enter circulation times for samples with forward-angle summaries to begin direct relationship analysis.")
        render_filtration_follow_up(samples)
        return

    trend_table = pd.DataFrame(
        {
            "Sample": [point.sample for point in analysis.points],
            "Entered Circulation Time": [point.circulation_time_value for point in analysis.points],
            "Unit": [point.circulation_time_unit for point in analysis.points],
            "Circulation Time (min)": [point.circulation_time for point in analysis.points],
            "Forward Z-Average": [point.forward_z_average for point in analysis.points],
            "Forward PDI": [point.forward_pdi for point in analysis.points],
        }
    )
    display = trend_table.copy()
    display["Entered Circulation Time"] = pd.to_numeric(display["Entered Circulation Time"], errors="coerce").round(3)
    display["Circulation Time (min)"] = pd.to_numeric(display["Circulation Time (min)"], errors="coerce").round(3)
    display["Forward Z-Average"] = pd.to_numeric(display["Forward Z-Average"], errors="coerce").round(1)
    display["Forward PDI"] = pd.to_numeric(display["Forward PDI"], errors="coerce").round(3)
    st.dataframe(display, use_container_width=True, hide_index=True)

    chart_columns = st.columns(2)
    with chart_columns[0]:
        st.plotly_chart(
            _forward_scatter_trend_chart(
                analysis.points,
                "forward_z_average",
                "Forward Z-Average vs Total Circulation Time",
                "Forward Z-Average (nm)",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
        render_relationship_summary(analysis.z_average)
    with chart_columns[1]:
        st.plotly_chart(
            _forward_scatter_trend_chart(
                analysis.points,
                "forward_pdi",
                "Forward PDI vs Total Circulation Time",
                "Forward PDI",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
        render_relationship_summary(analysis.pdi)

    render_filtration_follow_up(samples)


def parse_optional_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_filtration_score(value: str | float | int | None) -> int | None:
    if isinstance(value, str) and " - " in value:
        value = value.split(" - ", 1)[0]
    return validate_difficulty_score(value)


def _forward_scatter_trend_chart(
    points: list[ForwardScatterPoint],
    value_attribute: str,
    title: str,
    y_title: str,
) -> go.Figure:
    chart_points = [
        point
        for point in points
        if getattr(point, value_attribute) is not None and not pd.isna(getattr(point, value_attribute))
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[point.circulation_time for point in chart_points],
            y=[getattr(point, value_attribute) for point in chart_points],
            mode="markers+text",
            text=[point.sample for point in chart_points],
            textposition="top center",
            marker={"size": 11, "color": "#2563eb", "line": {"width": 1, "color": "#1e3a8a"}},
            hovertemplate="<b>%{text}</b><br>Circulation time: %{x:.3g}<br>%{y:.3g}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        height=340,
        title=title,
        margin={"l": 52, "r": 24, "t": 52, "b": 58},
        xaxis={"title": "Total Circulation Time (min)", "gridcolor": "#e8eef5"},
        yaxis={"title": y_title, "gridcolor": "#e8eef5"},
    )
    return figure


def render_relationship_summary(analysis: RelationshipAnalysis) -> None:
    if analysis.correlation is None:
        st.info(analysis.message)
    else:
        st.metric(f"{analysis.metric} correlation", f"{analysis.method} r = {analysis.correlation:.2f}", analysis.relationship)
        st.caption(analysis.message)


def render_filtration_hypothesis_callout() -> None:
    st.info(
        "Working hypothesis: total circulation time may relate to forward-scatter size/PDI, "
        "and those forward-scatter attributes may relate to filtration difficulty. "
        "The planned filtration device run is an orthogonal follow-up measurement; it may strengthen or weaken this relationship hypothesis."
    )


def render_filtration_follow_up(samples: list[ParsedSample]) -> None:
    render_filtration_hypothesis_callout()
    st.subheader("Filtration Follow-Up")
    st.caption(
        "Orthogonal filtration measurements can be entered manually or imported from a simple CSV. "
        "Difficulty is an ordinal operator-assessed score, not a continuous physical measurement."
    )

    render_filtration_rubric()
    manual_tab, csv_tab = st.tabs(["Manual Entry", "CSV Import"])
    with manual_tab:
        render_manual_filtration_entry(samples)
    with csv_tab:
        render_filtration_csv_import(samples)

    apply_session_experimental_variables(samples)
    render_attached_filtration_measurements(samples)

    filtration_analysis = build_filtration_trend_analysis(samples)
    if not filtration_analysis.points:
        st.info("Attach filtration difficulty scores for at least three samples to compare filtration behavior with DLS forward-scatter attributes.")
        return

    render_filtration_trend_table(filtration_analysis.points)
    chart_columns = st.columns(3)
    with chart_columns[0]:
        st.plotly_chart(
            _filtration_trend_chart(
                filtration_analysis.points,
                "forward_z_average",
                "Forward Z-Average vs Filtration Difficulty",
                "Forward Z-Average (nm)",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
        render_relationship_summary(filtration_analysis.z_average)
    with chart_columns[1]:
        st.plotly_chart(
            _filtration_trend_chart(
                filtration_analysis.points,
                "forward_pdi",
                "Forward PDI vs Filtration Difficulty",
                "Forward PDI",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
        render_relationship_summary(filtration_analysis.pdi)
    with chart_columns[2]:
        st.plotly_chart(
            _filtration_trend_chart(
                filtration_analysis.points,
                "circulation_time_minutes",
                "Circulation Time vs Filtration Difficulty",
                "Circulation Time (min)",
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
        render_relationship_summary(filtration_analysis.circulation_time)


def render_filtration_rubric() -> None:
    rubric = pd.DataFrame(
        [{"Score": score, "Meaning": meaning} for score, meaning in FILTRATION_DIFFICULTY_RUBRIC.items()]
    )
    st.markdown("**Ordinal difficulty rubric**")
    st.dataframe(rubric, use_container_width=True, hide_index=True)


def render_manual_filtration_entry(samples: list[ParsedSample]) -> None:
    columns = st.columns(min(3, len(samples)))
    invalid_pressure: list[str] = []
    for index, sample in enumerate(samples):
        existing = filtration_measurement_from_provenance(sample.measurement)
        _prefill_filtration_session(sample.name, existing)
        difficulty_key = f"filtration_difficulty::{sample.name}"
        time_key = f"filtration_time::{sample.name}"
        pressure_key = f"filtration_pressure::{sample.name}"
        pressure_unit_key = f"filtration_pressure_unit::{sample.name}"
        filter_key = f"filtration_filter::{sample.name}"
        clogging_key = f"filtration_clogging::{sample.name}"
        notes_key = f"filtration_notes::{sample.name}"

        with columns[index % len(columns)]:
            st.markdown(f"**{sample.name}**")
            score_labels = ["Not recorded"] + [
                f"{score} - {meaning}" for score, meaning in FILTRATION_DIFFICULTY_RUBRIC.items()
            ]
            st.selectbox(
                "Ordinal difficulty score",
                score_labels,
                key=difficulty_key,
                help="Operator-assessed ordinal score. Use the rubric above; do not treat as a continuous physical measurement.",
            )
            st.text_input("Filtration time (min)", key=time_key, placeholder="optional")
            pressure = st.text_input("Pressure", key=pressure_key, placeholder="optional")
            st.selectbox(
                "Pressure unit",
                [""] + list(PRESSURE_UNIT_LABELS),
                format_func=lambda unit: PRESSURE_UNIT_LABELS.get(unit, "Select unit"),
                key=pressure_unit_key,
                help="Pressure is stored in the original unit and normalized to kPa.",
            )
            st.text_input("Filter type", key=filter_key, placeholder="optional")
            st.selectbox("Clogging observed", ["Not recorded", "No", "Yes"], key=clogging_key)
            st.text_area("Notes", key=notes_key, height=70)
            parsed_pressure = parse_optional_float(pressure)
            if parsed_pressure is not None:
                pressure_unit = st.session_state.get(pressure_unit_key)
                if pressure_unit in PRESSURE_UNITS_TO_KPA:
                    st.caption(f"Normalized pressure: {normalize_pressure(parsed_pressure, pressure_unit):.3g} kPa")
                else:
                    st.warning("Select a supported pressure unit to normalize pressure.")
            elif str(pressure).strip():
                invalid_pressure.append(sample.name)

    if invalid_pressure:
        st.warning("Enter numeric pressure values for: " + ", ".join(invalid_pressure))


def _prefill_filtration_session(sample_name: str, existing: FiltrationMeasurement | None, *, overwrite: bool = False) -> None:
    if existing is None:
        return
    difficulty_key = f"filtration_difficulty::{sample_name}"
    if (overwrite or difficulty_key not in st.session_state) and existing.difficulty_score is not None:
        score = int(existing.difficulty_score)
        st.session_state[difficulty_key] = f"{score} - {FILTRATION_DIFFICULTY_RUBRIC.get(score, '')}"
    values = {
        f"filtration_time::{sample_name}": existing.filtration_time_minutes,
        f"filtration_pressure::{sample_name}": existing.pressure,
        f"filtration_pressure_unit::{sample_name}": existing.pressure_unit,
        f"filtration_filter::{sample_name}": existing.filter_type,
        f"filtration_notes::{sample_name}": existing.notes,
    }
    for key, value in values.items():
        if (overwrite or key not in st.session_state) and value not in (None, ""):
            st.session_state[key] = str(value)
    clogging_key = f"filtration_clogging::{sample_name}"
    if (overwrite or clogging_key not in st.session_state) and existing.clogging_observed is not None:
        st.session_state[clogging_key] = "Yes" if existing.clogging_observed else "No"


def render_filtration_csv_import(samples: list[ParsedSample]) -> None:
    st.caption("Supported CSV columns: sample name, difficulty score, filtration time, filtration time unit, pressure, pressure unit, filter type, clogging observed, notes.")
    filtration_file = st.file_uploader("Upload filtration CSV", type=["csv"], accept_multiple_files=False, key="filtration_csv_upload")
    if filtration_file is None:
        return
    result = parse_filtration_csv(filtration_file, source_name=filtration_file.name)
    render_filtration_import_preview(result)
    if result.measurements and st.button("Attach parsed filtration measurements", use_container_width=True):
        attached, unmatched = attach_filtration_measurements(samples, result.measurements)
        st.success(f"Attached filtration measurements to {attached} sample(s).")
        if unmatched:
            st.warning("No matching current DLS sample for: " + ", ".join(unmatched))


def render_filtration_import_preview(result: FiltrationImportResult) -> None:
    if result.missing_columns:
        st.error("Missing required columns: " + ", ".join(result.missing_columns))
    if result.unsupported_columns:
        st.caption("Unsupported columns ignored: " + ", ".join(result.unsupported_columns))
    for warning in result.warnings[:8]:
        st.warning(warning)
    for error in result.errors:
        st.error(error)
    if result.measurements:
        st.dataframe(
            pd.DataFrame([filtration_measurement_to_table_row(measurement) for measurement in result.measurements]),
            use_container_width=True,
            hide_index=True,
        )


def attach_filtration_measurements(samples: list[ParsedSample], measurements: list[FiltrationMeasurement]) -> tuple[int, list[str]]:
    by_name = {sample.name: sample for sample in samples}
    attached = 0
    unmatched = []
    for measurement in measurements:
        sample = by_name.get(measurement.sample_name)
        if sample is None:
            unmatched.append(measurement.sample_name)
            continue
        apply_filtration_measurement(sample.measurement, measurement)
        _prefill_filtration_session(sample.name, measurement, overwrite=True)
        attached += 1
    return attached, unmatched


def render_attached_filtration_measurements(samples: list[ParsedSample]) -> None:
    measurements = [
        measurement
        for sample in samples
        if (measurement := filtration_measurement_from_provenance(sample.measurement)) is not None
    ]
    if not measurements:
        return
    st.markdown("**Current attached filtration measurements**")
    st.dataframe(
        pd.DataFrame([filtration_measurement_to_table_row(measurement) for measurement in measurements]),
        use_container_width=True,
        hide_index=True,
    )


def render_filtration_trend_table(points: list[FiltrationTrendPoint]) -> None:
    table = pd.DataFrame(
        {
            "Sample": [point.sample for point in points],
            "Difficulty Score": [point.difficulty_score for point in points],
            "Forward Z-Average": [point.forward_z_average for point in points],
            "Forward PDI": [point.forward_pdi for point in points],
            "Circulation Time (min)": [point.circulation_time_minutes for point in points],
        }
    )
    display = table.copy()
    for column in ["Difficulty Score", "Forward Z-Average", "Circulation Time (min)"]:
        display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
    display["Forward PDI"] = pd.to_numeric(display["Forward PDI"], errors="coerce").round(3)
    st.dataframe(display, use_container_width=True, hide_index=True)


def _filtration_trend_chart(
    points: list[FiltrationTrendPoint],
    value_attribute: str,
    title: str,
    y_title: str,
) -> go.Figure:
    chart_points = [
        point
        for point in points
        if getattr(point, value_attribute) is not None and not pd.isna(getattr(point, value_attribute))
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[point.difficulty_score for point in chart_points],
            y=[getattr(point, value_attribute) for point in chart_points],
            mode="markers+text",
            text=[point.sample for point in chart_points],
            textposition="top center",
            marker={"size": 11, "color": "#0f766e", "line": {"width": 1, "color": "#134e4a"}},
            hovertemplate="<b>%{text}</b><br>Filtration difficulty: %{x:.3g}<br>%{y:.3g}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        height=330,
        title=title,
        margin={"l": 52, "r": 24, "t": 52, "b": 58},
        xaxis={"title": "Filtration Difficulty Score", "gridcolor": "#e8eef5"},
        yaxis={"title": y_title, "gridcolor": "#e8eef5"},
    )
    return figure


def render_aggregation_detection(samples: list[ParsedSample]) -> None:
    """Supporting dual-angle comparison panel.

    Renders only when at least one sample has a forward + backscatter angle pair.
    """
    assessments = [(sample, assess_dual_angle_aggregation(sample.measurement)) for sample in samples]
    available = [(sample, assessment) for sample, assessment in assessments if assessment.available]
    if not available:
        return

    st.subheader("Dual-Angle Comparison (Supporting Evidence)")
    st.caption(
        "Forward scatter (~12.8°) is far more sensitive to large species than backscatter "
        "(~173°). Aggregation Index = Z-average(forward) / Z-average(backscatter) − 1. Near 0 "
        "the angles agree; an elevated index points to forward-angle large-species enrichment — a "
        "screening signal that requires corroboration, not proof of aggregation. For this larger-particle "
        "system, the direct forward-scatter relationship to explicitly entered experiment variables is the "
        "primary trend analysis; the Aggregation Index does not gate or override it. The Malvern-derived "
        "Aggregation Index was designed for small-protein aggregation around 1-10 nm, so its published "
        "reference thresholds may not transfer directly here. Reference baseline (Malvern AN101104/AN140527): "
        "~0.05 stable, ~0.1 at aggregation onset."
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

    st.markdown("**Corroboration checklist** — supporting evidence for the dual-angle comparison")
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
    Dual-Angle Comparison panel; this is the full per-angle table with
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
    st.caption("Experiment intelligence platform: DLS review plus chromatography/mass-balance proof of concept")

    with st.sidebar:
        st.header("Data")
        uploaded_files = st.file_uploader("Upload DLS files", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
        st.divider()
        st.header("Chromatography Preview")
        chromatography_file = st.file_uploader("Upload chromatography CSV or OpenLab .olax", type=["csv", "olax"], accept_multiple_files=False)
        load_fixture = st.button("Load sample chromatography fixture", use_container_width=True)

    chromatography_preview = None
    chromatography_error = None
    if chromatography_file is not None:
        try:
            chromatography_preview = load_chromatography_preview(chromatography_file)
        except Exception as exc:  # pragma: no cover - surfaced in Streamlit
            chromatography_error = str(exc)
    elif load_fixture:
        try:
            chromatography_preview = load_chromatography_preview(CHROMATOGRAPHY_FIXTURE_PATH)
        except Exception as exc:  # pragma: no cover - surfaced in Streamlit
            chromatography_error = str(exc)

    if not uploaded_files and not st.session_state.get("imported_samples"):
        st.session_state.pop("imported_upload_signature", None)
        st.session_state.pop("imported_samples", None)
        st.session_state.pop("import_errors", None)
        render_empty_state()
        render_saved_experiment_loader()
        if chromatography_error:
            st.error(f"Chromatography preview failed: {chromatography_error}")
        if chromatography_preview is not None:
            render_chromatography_preview(chromatography_preview)
            render_memory_panel(
                chromatography_experiment=chromatography_experiment_from_preview(
                    chromatography_preview,
                    label="Chromatography preview",
                    source_name=chromatography_preview.get("source_name"),
                )
            )
        else:
            render_memory_panel()
        render_research_journal_panel()
        return

    preview = None
    if uploaded_files:
        upload_signature = upload_batch_signature(uploaded_files)
        if st.session_state.get("imported_upload_signature") != upload_signature:
            st.session_state.pop("imported_samples", None)
            st.session_state.pop("import_errors", None)

        preview = build_import_preview(uploaded_files)
        if st.session_state.get("imported_upload_signature") != upload_signature:
            import_preview_to_session(preview, upload_signature)

    has_imported_samples = bool(st.session_state.get("imported_samples"))
    with st.sidebar:
        if preview is not None:
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

    apply_session_experimental_variables(samples)

    with st.sidebar:
        st.divider()
        st.header("History")
        loaded_record = st.session_state.get("loaded_history_record")
        if loaded_record:
            st.caption(f"Loaded saved version: {loaded_record.get('label')} ({str(loaded_record.get('id', ''))[:8]}). Saving appends a new version.")
        history_label = st.text_input("Experiment label", value=st.session_state.get("history_label", ""), key="history_label")
        if st.button("Save current experiment", use_container_width=True):
            for sample in samples:
                if loaded_record:
                    sample.measurement.provenance["history_lineage"] = {
                        "loaded_from_record_id": loaded_record.get("id"),
                        "loaded_from_label": loaded_record.get("label"),
                        "save_semantics": "append_new_version",
                    }
            record = save_experiment([sample.measurement for sample in samples], history_label)
            st.success(f"Saved {record.label}")
        st.divider()
        st.header("Report")
        st.button("Export report", use_container_width=True, disabled=True, help="Report export is coming in a future version.")
        st.caption("Report export is coming soon.")

    metrics = build_metrics_table(samples)
    source_file_names = [uploaded_file.name for uploaded_file in uploaded_files] if uploaded_files else [sample.file_name for sample in samples if sample.file_name]
    dls_memory_experiment = dls_experiment_from_samples(
        samples,
        label=history_label or "DLS experiment",
        source_files=source_file_names,
    )
    chromatography_memory_experiment = (
        chromatography_experiment_from_preview(
            chromatography_preview,
            label="Chromatography preview",
            source_name=chromatography_preview.get("source_name"),
        )
        if chromatography_preview is not None
        else None
    )

    render_decision_workbench(samples, metrics)
    if chromatography_error:
        st.error(f"Chromatography preview failed: {chromatography_error}")
    if chromatography_preview is not None:
        render_chromatography_preview(chromatography_preview)
    if preview is not None:
        render_data_completeness(preview.groups)
    render_forward_scatter_trend_explorer(samples)
    render_aggregation_detection(samples)
    if preview is not None:
        render_import_details(preview, import_errors)
    render_history_panel(samples)
    render_memory_panel(
        dls_experiment=dls_memory_experiment,
        chromatography_experiment=chromatography_memory_experiment,
    )
    render_research_journal_panel()

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
        render_ai_summary(samples, metrics)

        replicate_stats = replicate_statistics_table(samples)
        if not replicate_stats.empty:
            st.subheader("Replicate Trend Statistics")
            display = replicate_stats.copy()
            for column in ["Mean", "SD", "%RSD"]:
                display[column] = pd.to_numeric(display[column], errors="coerce").round(3)
            st.dataframe(display, use_container_width=True, hide_index=True)

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
