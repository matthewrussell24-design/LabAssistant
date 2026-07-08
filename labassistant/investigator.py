"""Scientific Investigator: deterministic reasoning over Observations.

The Investigator is the first piece of LabAssistant's instrument-agnostic
intelligence layer. It consumes ``Observation`` objects only -- never raw files
and never ``Measurement``/``ChromatographyMeasurement`` objects -- so the same
engine reasons about DLS, HPLC, SEC, UV-Vis, ELISA, DSC and any future
technique as long as an importer emits Observations.

It answers five questions with no LLM:

    What happened?
    Is the experiment complete?
    Is anything missing?
    Can the experiment be interpreted?
    What additional information would improve confidence?

Conventions the reasoning relies on (shared across all importers):

* Observations that describe a *gap* (missing/undecoded/unknown data that limits
  interpretation) use ``category == "data_completeness"``.
* ``severity`` is one of ``review`` (blocks confident interpretation),
  ``watch`` (limits interpretation), ``normal``/``info`` (positive or neutral).
* A completeness gap at ``review`` severity is treated as an interpretation
  *blocker*; at ``watch`` severity it is a *limitation* that lowers confidence.
"""

from __future__ import annotations

from typing import Iterable

from labassistant.models import Experiment, InvestigatorFinding, InvestigatorReport, Observation


DATA_COMPLETENESS_CATEGORY = "data_completeness"
BLOCKING_SEVERITY = "review"
LIMITING_SEVERITY = "watch"


def investigate(experiment: Experiment) -> InvestigatorReport:
    """Reason over an Experiment's Observation stream."""
    return investigate_observations(
        experiment.observations,
        experiment_id=experiment.experiment_id,
        technique=experiment.technique,
    )


def investigate_observations(
    observations: Iterable[Observation],
    *,
    experiment_id: str = "",
    technique: str | None = None,
) -> InvestigatorReport:
    """Reason over a bare Observation stream (works without an Experiment)."""
    observations = list(observations)
    counts = _severity_counts(observations)

    completeness = [o for o in observations if o.category == DATA_COMPLETENESS_CATEGORY]
    blockers = [o for o in completeness if o.severity == BLOCKING_SEVERITY]
    limitations = [o for o in completeness if o.severity == LIMITING_SEVERITY]
    content = [o for o in observations if o.category != DATA_COMPLETENESS_CATEGORY]

    is_complete = not completeness
    has_content = bool(content)
    # Interpretable when there is substantive evidence and no hard blocker.
    is_interpretable = has_content and not blockers

    completeness_gaps = [_gap_text(o) for o in completeness]
    interpretation_blockers = [_gap_text(o) for o in blockers]
    if not has_content:
        interpretation_blockers.append("No substantive observations were produced to interpret.")

    confidence_improvers = _confidence_improvers(completeness, observations)
    highlights = _highlights(observations)

    what_happened = _what_happened(observations, counts, technique)

    findings = [
        InvestigatorFinding(
            question="What happened?",
            answer=what_happened,
            details=highlights,
        ),
        InvestigatorFinding(
            question="Is the experiment complete?",
            answer="Complete." if is_complete else f"Incomplete ({len(completeness)} gap(s)).",
            details=completeness_gaps,
        ),
        InvestigatorFinding(
            question="Is anything missing?",
            answer=(
                "Nothing flagged by current rules."
                if not completeness
                else f"{len(completeness)} item(s) flagged as missing or undecoded."
            ),
            details=completeness_gaps,
        ),
        InvestigatorFinding(
            question="Can the experiment be interpreted?",
            answer=_interpretability_answer(is_interpretable, blockers, limitations, has_content),
            details=interpretation_blockers or [_limitation_text(o) for o in limitations],
        ),
        InvestigatorFinding(
            question="What additional information would improve confidence?",
            answer=(
                "No additional information required by current rules."
                if not confidence_improvers
                else f"{len(confidence_improvers)} suggestion(s)."
            ),
            details=confidence_improvers,
        ),
    ]

    return InvestigatorReport(
        experiment_id=experiment_id,
        what_happened=what_happened,
        is_complete=is_complete,
        is_interpretable=is_interpretable,
        completeness_gaps=completeness_gaps,
        interpretation_blockers=interpretation_blockers,
        confidence_improvers=confidence_improvers,
        highlights=highlights,
        findings=findings,
        observation_counts=counts,
    )


def _severity_counts(observations: list[Observation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        severity = observation.severity or "info"
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _what_happened(
    observations: list[Observation],
    counts: dict[str, int],
    technique: str | None,
) -> str:
    if not observations:
        return "No observations were generated; there is nothing to interpret yet."

    technique_label = f"{technique} experiment" if technique else "Experiment"
    review = counts.get("review", 0)
    watch = counts.get("watch", 0)
    positive = counts.get("normal", 0) + counts.get("info", 0)

    parts = [f"{technique_label}: {len(observations)} observation(s)"]
    detail = []
    if review:
        detail.append(f"{review} need review")
    if watch:
        detail.append(f"{watch} to watch")
    if positive:
        detail.append(f"{positive} normal/informational")
    if detail:
        parts.append("(" + ", ".join(detail) + ")")
    return " ".join(parts) + "."


def _interpretability_answer(
    is_interpretable: bool,
    blockers: list[Observation],
    limitations: list[Observation],
    has_content: bool,
) -> str:
    if not has_content:
        return "No -- there is no substantive evidence to interpret."
    if blockers:
        return "No -- interpretation is blocked by missing critical data."
    if limitations:
        return "Partially -- qualitative interpretation is possible, but data gaps limit confidence."
    return "Yes -- the available evidence supports interpretation."


def _confidence_improvers(
    completeness: list[Observation],
    observations: list[Observation],
) -> list[str]:
    improvers: list[str] = []
    seen: set[str] = set()

    # Completeness gaps first -- closing them has the biggest confidence impact.
    for observation in completeness:
        text = observation.recommendation or f"Resolve gap: {observation.label}."
        if text not in seen:
            improvers.append(text)
            seen.add(text)

    # Then any other recommendation attached to review/watch observations.
    for observation in observations:
        if observation.category == DATA_COMPLETENESS_CATEGORY:
            continue
        if observation.severity not in {BLOCKING_SEVERITY, LIMITING_SEVERITY}:
            continue
        if observation.recommendation and observation.recommendation not in seen:
            improvers.append(observation.recommendation)
            seen.add(observation.recommendation)

    return improvers


def _highlights(observations: list[Observation]) -> list[str]:
    order = {"review": 0, "watch": 1, "normal": 2, "info": 3}
    ranked = sorted(
        observations,
        key=lambda o: (order.get(o.severity, 4), o.label),
    )
    highlights: list[str] = []
    seen: set[str] = set()
    for observation in ranked:
        if observation.label in seen:
            continue
        seen.add(observation.label)
        prefix = f"[{observation.severity}] " if observation.severity in {"review", "watch"} else ""
        sample = f"{observation.sample_name}: " if observation.sample_name else ""
        highlights.append(f"{prefix}{sample}{observation.label} — {observation.evidence}")
        if len(highlights) >= 6:
            break
    return highlights


def _gap_text(observation: Observation) -> str:
    return f"{observation.label}: {observation.evidence}"


def _limitation_text(observation: Observation) -> str:
    return f"{observation.label} limits interpretation: {observation.evidence}"
