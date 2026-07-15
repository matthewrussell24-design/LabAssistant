from __future__ import annotations

import json
import re
import sqlite3
from hashlib import sha256
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from labassistant.models import Experiment, Observation
from labassistant.runtime_paths import resolve_runtime_paths


DEFAULT_KNOWLEDGE_STORE_PATH = resolve_runtime_paths().knowledge_store_path


def default_knowledge_store_path() -> Path:
    """Resolve the implicit knowledge-store path lazily."""
    return resolve_runtime_paths().knowledge_store_path

MEMORY_EXPERIMENT = "experiment"
MEMORY_PROJECT = "project"
MEMORY_INSTRUMENT = "instrument"
MEMORY_SCIENTIFIC = "scientific"
MEMORY_HUMAN_NOTE = "human_note"

ENTITY_EXPERIMENT = "experiment"
ENTITY_MEASUREMENT = "measurement"
ENTITY_OBSERVATION = "observation"
ENTITY_EVIDENCE = "evidence"
ENTITY_HYPOTHESIS = "hypothesis"
ENTITY_RECOMMENDATION = "recommendation"
ENTITY_NOTE = "note"
ENTITY_SOURCE_FILE = "source_file"


@dataclass
class KnowledgeItem:
    """One persisted memory item in LabAssistant's local knowledge store."""

    item_id: str
    layer: str
    entity_type: str
    title: str
    text: str
    experiment_id: str | None = None
    project_id: str | None = None
    instrument_id: str | None = None
    source_id: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: str = "medium"
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextPacket:
    """Compact deterministic context assembled for a user question."""

    question: str
    relevant_experiments: list[KnowledgeItem] = field(default_factory=list)
    relevant_observations: list[KnowledgeItem] = field(default_factory=list)
    supporting_evidence: list[KnowledgeItem] = field(default_factory=list)
    hypotheses: list[KnowledgeItem] = field(default_factory=list)
    recommendations: list[KnowledgeItem] = field(default_factory=list)
    related_notes: list[KnowledgeItem] = field(default_factory=list)
    source_files: list[KnowledgeItem] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    confidence: str = "low"
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "relevant_experiments": [item.to_dict() for item in self.relevant_experiments],
            "relevant_observations": [item.to_dict() for item in self.relevant_observations],
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "recommendations": [item.to_dict() for item in self.recommendations],
            "related_notes": [item.to_dict() for item in self.related_notes],
            "source_files": [item.to_dict() for item in self.source_files],
            "missing_information": list(self.missing_information),
            "confidence": self.confidence,
            "caveats": list(self.caveats),
        }


@dataclass
class ResearchJournalEntry:
    """Human-readable journal view over persisted knowledge items."""

    entry_id: str
    created_at: str
    title: str
    experiment_id: str | None = None
    instrument: str | None = None
    tags: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    key_observations: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KnowledgeStore:
    """Small local SQLite knowledge store for experiments and scientific memory."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_knowledge_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def add_item(
        self,
        *,
        layer: str,
        entity_type: str,
        title: str,
        text: str,
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        source_id: str | None = None,
        tags: Iterable[str] = (),
        confidence: str = "medium",
        payload: dict[str, Any] | None = None,
        item_id: str | None = None,
        created_at: str | None = None,
    ) -> KnowledgeItem:
        item = KnowledgeItem(
            item_id=item_id or _stable_item_id(layer, entity_type, title, text, experiment_id, source_id),
            layer=layer,
            entity_type=entity_type,
            title=title,
            text=text,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            source_id=source_id,
            tags=sorted(set(_normalize_tag(tag) for tag in tags if tag)),
            confidence=confidence,
            payload=payload or {},
            created_at=created_at or _utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO knowledge_items (
                    item_id, layer, entity_type, title, text, experiment_id,
                    project_id, instrument_id, source_id, tags, confidence,
                    payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.item_id,
                    item.layer,
                    item.entity_type,
                    item.title,
                    item.text,
                    item.experiment_id,
                    item.project_id,
                    item.instrument_id,
                    item.source_id,
                    json.dumps(item.tags, sort_keys=True),
                    item.confidence,
                    json.dumps(item.payload, sort_keys=True, default=str),
                    item.created_at,
                ),
            )
        return item

    def add_experiment(
        self,
        experiment: Experiment,
        *,
        project_id: str | None = None,
        tags: Iterable[str] = (),
    ) -> None:
        experiment_tags = set(tags)
        if experiment.technique:
            experiment_tags.add(experiment.technique)
        if experiment.instrument:
            experiment_tags.add(experiment.instrument)
        experiment_id = experiment.experiment_id
        source_files = _experiment_source_files(experiment)

        self.add_item(
            layer=MEMORY_EXPERIMENT,
            entity_type=ENTITY_EXPERIMENT,
            title=experiment.label,
            text=_experiment_text(experiment),
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=experiment.instrument,
            source_id=experiment.source_path,
            tags=experiment_tags,
            confidence="high",
            payload=experiment.to_dict(),
            created_at=experiment.created_at,
        )

        for index, measurement in enumerate(experiment.measurements, start=1):
            payload = measurement.to_dict() if hasattr(measurement, "to_dict") else measurement
            title = _measurement_title(payload, index)
            self.add_item(
                layer=MEMORY_EXPERIMENT,
                entity_type=ENTITY_MEASUREMENT,
                title=title,
                text=_measurement_text(payload),
                experiment_id=experiment_id,
                project_id=project_id,
                instrument_id=experiment.instrument,
                source_id=str(payload.get("injection_id") or title) if isinstance(payload, dict) else title,
                tags=experiment_tags,
                confidence="medium",
                payload=payload if isinstance(payload, dict) else {"value": payload},
            )

        for index, observation in enumerate(experiment.observations, start=1):
            self.add_observation(
                observation,
                experiment_id=experiment_id,
                project_id=project_id,
                instrument_id=experiment.instrument,
                source_id=observation.source_id or f"{experiment_id}:observation:{index}",
                tags=experiment_tags | {observation.category, observation.severity},
            )

        for section in experiment.unsupported_sections:
            self.add_item(
                layer=MEMORY_EXPERIMENT,
                entity_type=ENTITY_EVIDENCE,
                title="Unsupported section",
                text=section,
                experiment_id=experiment_id,
                project_id=project_id,
                instrument_id=experiment.instrument,
                source_id=experiment.source_path,
                tags=experiment_tags | {"unsupported", "missing_information"},
                confidence="high",
            )

        for source_file in source_files:
            self.add_source_file(
                source_file,
                experiment_id=experiment_id,
                project_id=project_id,
                instrument_id=experiment.instrument,
                tags=experiment_tags,
            )

    def add_observation(
        self,
        observation: Observation,
        *,
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        source_id: str | None = None,
        tags: Iterable[str] = (),
    ) -> KnowledgeItem:
        item = self.add_item(
            layer=MEMORY_EXPERIMENT,
            entity_type=ENTITY_OBSERVATION,
            title=observation.label,
            text=observation.evidence,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            source_id=source_id or observation.source_id,
            tags=tags,
            confidence=observation.confidence,
            payload=asdict(observation),
        )
        if observation.recommendation:
            self.add_recommendation(
                observation.recommendation,
                experiment_id=experiment_id,
                project_id=project_id,
                instrument_id=instrument_id,
                source_id=item.item_id,
                tags=tags,
            )
        return item

    def add_hypothesis(
        self,
        text: str,
        *,
        title: str = "Hypothesis",
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        source_id: str | None = None,
        tags: Iterable[str] = (),
        confidence: str = "medium",
    ) -> KnowledgeItem:
        return self.add_item(
            layer=MEMORY_SCIENTIFIC,
            entity_type=ENTITY_HYPOTHESIS,
            title=title,
            text=text,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            source_id=source_id,
            tags=tags,
            confidence=confidence,
        )

    def add_recommendation(
        self,
        text: str,
        *,
        title: str = "Recommendation",
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        source_id: str | None = None,
        tags: Iterable[str] = (),
        confidence: str = "medium",
    ) -> KnowledgeItem:
        return self.add_item(
            layer=MEMORY_SCIENTIFIC,
            entity_type=ENTITY_RECOMMENDATION,
            title=title,
            text=text,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            source_id=source_id,
            tags=tags,
            confidence=confidence,
        )

    def add_note(
        self,
        text: str,
        *,
        title: str = "Note",
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        tags: Iterable[str] = (),
    ) -> KnowledgeItem:
        return self.add_item(
            layer=MEMORY_HUMAN_NOTE,
            entity_type=ENTITY_NOTE,
            title=title,
            text=text,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            tags=tags,
            confidence="human",
        )

    def add_source_file(
        self,
        path: str,
        *,
        experiment_id: str | None = None,
        project_id: str | None = None,
        instrument_id: str | None = None,
        tags: Iterable[str] = (),
    ) -> KnowledgeItem:
        return self.add_item(
            layer=MEMORY_EXPERIMENT,
            entity_type=ENTITY_SOURCE_FILE,
            title=Path(path).name,
            text=path,
            experiment_id=experiment_id,
            project_id=project_id,
            instrument_id=instrument_id,
            source_id=path,
            tags=tags,
            confidence="high",
            payload={"path": path},
        )

    def search(
        self,
        query: str,
        *,
        layers: Iterable[str] | None = None,
        entity_types: Iterable[str] | None = None,
        tags: Iterable[str] = (),
        limit: int = 25,
    ) -> list[KnowledgeItem]:
        tokens = _query_tokens(query)
        required_tags = {_normalize_tag(tag) for tag in tags if tag}
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM knowledge_items").fetchall()

        candidates = []
        layer_filter = set(layers or [])
        entity_filter = set(entity_types or [])
        for row in rows:
            item = _item_from_row(row)
            if layer_filter and item.layer not in layer_filter:
                continue
            if entity_filter and item.entity_type not in entity_filter:
                continue
            if required_tags and not required_tags <= set(item.tags):
                continue
            score = _score_item(item, tokens)
            if score > 0 or not tokens:
                candidates.append((score, item.created_at or "", item))

        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
        return [item for _, _, item in candidates[:limit]]

    def list_items(self, *, entity_type: str | None = None) -> list[KnowledgeItem]:
        sql = "SELECT * FROM knowledge_items"
        params: tuple[Any, ...] = ()
        if entity_type:
            sql += " WHERE entity_type = ?"
            params = (entity_type,)
        sql += " ORDER BY created_at DESC, title ASC"
        with self._connect() as connection:
            return [_item_from_row(row) for row in connection.execute(sql, params).fetchall()]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    item_id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    experiment_id TEXT,
                    project_id TEXT,
                    instrument_id TEXT,
                    source_id TEXT,
                    tags TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_layer ON knowledge_items(layer)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_entity ON knowledge_items(entity_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_experiment ON knowledge_items(experiment_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


class ResearchJournal:
    """Deterministic journal assembled from KnowledgeStore items."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def entries(
        self,
        *,
        keyword: str = "",
        tag: str = "",
        instrument: str = "",
        sample: str = "",
    ) -> list[ResearchJournalEntry]:
        entries = _journal_entries_from_items(self.store.list_items())
        return [
            entry
            for entry in entries
            if _journal_entry_matches(
                entry,
                keyword=keyword,
                tag=tag,
                instrument=instrument,
                sample=sample,
            )
        ]

    def export_markdown(
        self,
        *,
        keyword: str = "",
        tag: str = "",
        instrument: str = "",
        sample: str = "",
    ) -> str:
        entries = self.entries(keyword=keyword, tag=tag, instrument=instrument, sample=sample)
        lines = ["# LabAssistant Research Journal", ""]
        filters = []
        if keyword:
            filters.append(f"keyword: {keyword}")
        if tag:
            filters.append(f"tag: {tag}")
        if instrument:
            filters.append(f"instrument: {instrument}")
        if sample:
            filters.append(f"sample: {sample}")
        if filters:
            lines.extend([f"_Filters: {', '.join(filters)}_", ""])
        if not entries:
            lines.append("_No journal entries matched the current filters._")
            return "\n".join(lines) + "\n"

        for entry in entries:
            lines.extend(
                [
                    f"## {entry.title}",
                    "",
                    f"- Date/time: {entry.created_at or 'unknown'}",
                    f"- Instrument: {entry.instrument or 'unknown'}",
                ]
            )
            if entry.tags:
                lines.append(f"- Tags: {', '.join(entry.tags)}")
            if entry.samples:
                lines.append(f"- Samples: {', '.join(entry.samples)}")
            if entry.source_files:
                lines.append(f"- Source files: {', '.join(entry.source_files)}")
            lines.append("")
            _append_markdown_list(lines, "Key observations", entry.key_observations)
            _append_markdown_list(lines, "Hypotheses", entry.hypotheses)
            _append_markdown_list(lines, "Recommendations", entry.recommendations)
            _append_markdown_list(lines, "Notes", entry.notes)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


class ContextRetriever:
    """Assemble compact context packets from the local KnowledgeStore."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def retrieve(self, question: str, *, tags: Iterable[str] = (), limit: int = 6) -> ContextPacket:
        matches = self.store.search(question, tags=tags, limit=limit * 4)
        experiments = _limit_by_type(matches, ENTITY_EXPERIMENT, limit=3)
        observations = _limit_by_type(matches, ENTITY_OBSERVATION, limit=limit)
        evidence = _limit_by_type(matches, ENTITY_EVIDENCE, limit=limit)
        hypotheses = _limit_by_type(matches, ENTITY_HYPOTHESIS, limit=3)
        recommendations = _limit_by_type(matches, ENTITY_RECOMMENDATION, limit=3)
        notes = _limit_by_type(matches, ENTITY_NOTE, limit=3)
        source_files = _source_files_for(matches, self.store, limit=5)
        missing = _missing_information(matches)
        confidence = _packet_confidence(matches, observations, missing)
        caveats = _packet_caveats(matches, missing)
        return ContextPacket(
            question=question,
            relevant_experiments=experiments,
            relevant_observations=observations,
            supporting_evidence=evidence,
            hypotheses=hypotheses,
            recommendations=recommendations,
            related_notes=notes,
            source_files=source_files,
            missing_information=missing,
            confidence=confidence,
            caveats=caveats,
        )


def _item_from_row(row: sqlite3.Row) -> KnowledgeItem:
    return KnowledgeItem(
        item_id=row["item_id"],
        layer=row["layer"],
        entity_type=row["entity_type"],
        title=row["title"],
        text=row["text"],
        experiment_id=row["experiment_id"],
        project_id=row["project_id"],
        instrument_id=row["instrument_id"],
        source_id=row["source_id"],
        tags=list(json.loads(row["tags"] or "[]")),
        confidence=row["confidence"],
        payload=dict(json.loads(row["payload_json"] or "{}")),
        created_at=row["created_at"],
    )


def _journal_entries_from_items(items: list[KnowledgeItem]) -> list[ResearchJournalEntry]:
    by_experiment: dict[str, list[KnowledgeItem]] = {}
    standalone: list[KnowledgeItem] = []
    for item in items:
        if item.experiment_id:
            by_experiment.setdefault(item.experiment_id, []).append(item)
        elif item.entity_type == ENTITY_NOTE:
            standalone.append(item)

    entries = [_journal_entry_from_group(experiment_id, group) for experiment_id, group in by_experiment.items()]
    for note in standalone:
        entries.append(
            ResearchJournalEntry(
                entry_id=note.item_id,
                created_at=note.created_at or "",
                title=note.title,
                experiment_id=None,
                instrument=note.instrument_id,
                tags=list(note.tags),
                samples=[],
                notes=[note.text],
            )
        )
    return sorted(entries, key=lambda entry: entry.created_at or "", reverse=True)


def _journal_entry_from_group(experiment_id: str, items: list[KnowledgeItem]) -> ResearchJournalEntry:
    experiment = next((item for item in items if item.entity_type == ENTITY_EXPERIMENT), None)
    title = experiment.title if experiment else f"Experiment {experiment_id}"
    created_at = (experiment.created_at if experiment else None) or max((item.created_at or "" for item in items), default="")
    instrument = (experiment.instrument_id if experiment else None) or next(
        (item.instrument_id for item in items if item.instrument_id),
        None,
    )
    tags = sorted({tag for item in items for tag in item.tags})
    observations = [
        f"{item.title}: {item.text}"
        for item in items
        if item.entity_type == ENTITY_OBSERVATION
    ]
    samples = [
        item.title
        for item in items
        if item.entity_type == ENTITY_MEASUREMENT
    ]
    hypotheses = [item.text for item in items if item.entity_type == ENTITY_HYPOTHESIS]
    recommendations = [item.text for item in items if item.entity_type == ENTITY_RECOMMENDATION]
    source_files = [item.text for item in items if item.entity_type == ENTITY_SOURCE_FILE]
    notes = [item.text for item in items if item.entity_type == ENTITY_NOTE]
    evidence = [
        f"{item.title}: {item.text}"
        for item in items
        if item.entity_type == ENTITY_EVIDENCE and item.text not in observations
    ]
    return ResearchJournalEntry(
        entry_id=experiment_id,
        created_at=created_at,
        title=title,
        experiment_id=experiment_id,
        instrument=instrument,
        tags=tags,
        samples=_unique_text(samples),
        key_observations=_unique_text(observations + evidence),
        hypotheses=_unique_text(hypotheses),
        recommendations=_unique_text(recommendations),
        source_files=_unique_text(source_files),
        notes=_unique_text(notes),
    )


def _journal_entry_matches(
    entry: ResearchJournalEntry,
    *,
    keyword: str,
    tag: str,
    instrument: str,
    sample: str,
) -> bool:
    haystack = " ".join(
        [
            entry.title,
            entry.instrument or "",
            " ".join(entry.tags),
            " ".join(entry.samples),
            " ".join(entry.key_observations),
            " ".join(entry.hypotheses),
            " ".join(entry.recommendations),
            " ".join(entry.source_files),
            " ".join(entry.notes),
        ]
    ).lower()
    if keyword and not all(token in haystack for token in _query_tokens(keyword)):
        return False
    if tag and _normalize_tag(tag) not in set(entry.tags):
        return False
    if instrument and instrument.lower() not in (entry.instrument or "").lower():
        return False
    if sample and sample.lower() not in haystack:
        return False
    return True


def _append_markdown_list(lines: list[str], title: str, values: list[str]) -> None:
    lines.append(f"**{title}**")
    if not values:
        lines.append("- None recorded.")
    else:
        lines.extend(f"- {value}" for value in values)
    lines.append("")


def _unique_text(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _query_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) >= 2}


def _score_item(item: KnowledgeItem, tokens: set[str]) -> int:
    haystack = " ".join(
        [
            item.title,
            item.text,
            item.layer,
            item.entity_type,
            " ".join(item.tags),
            item.experiment_id or "",
            item.project_id or "",
            item.instrument_id or "",
        ]
    ).lower()
    score = sum(3 if token in item.title.lower() else 1 for token in tokens if token in haystack)
    if item.entity_type == ENTITY_EXPERIMENT and score:
        score += 1
    if item.entity_type == ENTITY_OBSERVATION and score:
        score += 2
    return score


def _limit_by_type(items: list[KnowledgeItem], entity_type: str, *, limit: int) -> list[KnowledgeItem]:
    selected = []
    seen = set()
    for item in items:
        if item.entity_type != entity_type or item.item_id in seen:
            continue
        selected.append(item)
        seen.add(item.item_id)
        if len(selected) >= limit:
            break
    return selected


def _source_files_for(items: list[KnowledgeItem], store: KnowledgeStore, *, limit: int) -> list[KnowledgeItem]:
    experiment_ids = {item.experiment_id for item in items if item.experiment_id}
    sources = []
    seen = set()
    for source in store.list_items(entity_type=ENTITY_SOURCE_FILE):
        if source.experiment_id not in experiment_ids or source.item_id in seen:
            continue
        sources.append(source)
        seen.add(source.item_id)
        if len(sources) >= limit:
            break
    return sources


def _missing_information(items: list[KnowledgeItem]) -> list[str]:
    missing = []
    seen = set()
    for item in items:
        payload = item.payload or {}
        label = str(payload.get("label") or item.title)
        category = str(payload.get("category") or "")
        severity = str(payload.get("severity") or "")
        if (
            "missing" in item.title.lower()
            or "unsupported" in item.title.lower()
            or category == "data_completeness"
            or "missing_information" in item.tags
        ):
            text = f"{label}: {item.text}"
            if severity:
                text += f" ({severity})"
            if text not in seen:
                missing.append(text)
                seen.add(text)
    return missing


def _packet_confidence(
    matches: list[KnowledgeItem],
    observations: list[KnowledgeItem],
    missing: list[str],
) -> str:
    if not matches:
        return "low"
    if missing:
        return "medium" if observations else "low"
    if any(item.confidence == "high" for item in observations):
        return "high"
    return "medium"


def _packet_caveats(matches: list[KnowledgeItem], missing: list[str]) -> list[str]:
    caveats = []
    if not matches:
        caveats.append("No matching local memory was found; import experiments or add notes first.")
    if missing:
        caveats.append("Some relevant memory items describe missing or unsupported information.")
    caveats.append("Context was assembled by deterministic keyword/tag retrieval; no LLM reasoning was used.")
    return caveats


def _experiment_text(experiment: Experiment) -> str:
    parts = [
        experiment.label,
        experiment.technique or "",
        experiment.instrument or "",
        f"{len(experiment.measurements)} measurement(s)",
        f"{len(experiment.observations)} observation(s)",
    ]
    if experiment.source_path:
        parts.append(experiment.source_path)
    for observation in experiment.observations[:10]:
        parts.extend([observation.label, observation.category, observation.evidence])
    return " | ".join(part for part in parts if part)


def _measurement_title(payload: Any, index: int) -> str:
    if isinstance(payload, dict):
        return str(
            payload.get("sample_name")
            or payload.get("metadata", {}).get("sample_name")
            or payload.get("injection_id")
            or f"Measurement {index}"
        )
    return f"Measurement {index}"


def _measurement_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)
    fields = [
        payload.get("sample_name"),
        payload.get("technique"),
        payload.get("method_name"),
        payload.get("injection_id"),
        payload.get("metadata", {}).get("sample_name") if isinstance(payload.get("metadata"), dict) else None,
        json.dumps(payload.get("summary_metrics", {}), sort_keys=True, default=str)
        if payload.get("summary_metrics")
        else None,
        json.dumps(payload.get("derived_metrics", {}), sort_keys=True, default=str)
        if payload.get("derived_metrics")
        else None,
    ]
    return " | ".join(str(field) for field in fields if field not in (None, "", "{}"))


def _experiment_source_files(experiment: Experiment) -> list[str]:
    sources = []
    if experiment.source_path:
        sources.append(experiment.source_path)
    metadata_sources = experiment.metadata.get("source_files", [])
    if isinstance(metadata_sources, list):
        sources.extend(str(path) for path in metadata_sources if path)
    for measurement in experiment.measurements:
        payload = measurement.to_dict() if hasattr(measurement, "to_dict") else measurement
        if isinstance(payload, dict):
            sources.extend(str(path) for path in payload.get("source_files", []) if path)
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict):
                sources.extend(str(path) for path in metadata.get("source_files", []) if path)
    return list(dict.fromkeys(sources))


def _normalize_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(tag).lower()).strip("_")


def _stable_item_id(
    layer: str,
    entity_type: str,
    title: str,
    text: str,
    experiment_id: str | None,
    source_id: str | None,
) -> str:
    base = "|".join([layer, entity_type, title, text, experiment_id or "", source_id or "", _utc_now()])
    return sha256(base.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
