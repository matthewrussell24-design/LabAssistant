"""Draft transport-neutral conformance for the first read-only API candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Callable

from labassistant.application import (
    AGENT_API_VERSION,
    ExperimentListing,
    agent_access_policy,
    app_manifest,
    list_experiments,
    retrieve_experiment,
    retrieve_history_overview,
    retrieve_related_context,
    retrieve_research_journal,
)
from labassistant.history import ExperimentRecordNotFoundError


INVALID_INPUT = "invalid_input"
NOT_FOUND = "not_found"
CONFLICT = "conflict"
UNSUPPORTED_EVIDENCE = "unsupported_evidence"
ACCESS_DENIED = "access_denied"
INTERNAL_FAILURE = "internal_failure"

ERROR_CODES = (
    INVALID_INPUT,
    NOT_FOUND,
    CONFLICT,
    UNSUPPORTED_EVIDENCE,
    ACCESS_DENIED,
    INTERNAL_FAILURE,
)

CANDIDATE_READS = (
    "describe_platform",
    "describe_agent_access",
    "list_experiments",
    "retrieve_history_overview",
    "retrieve_experiment",
    "retrieve_related_context",
    "retrieve_research_journal",
)

PROTECTED_READS = frozenset(CANDIDATE_READS[2:])

HISTORY_READ = "history:read"
MEMORY_READ = "memory:read"
LOCAL_CLIENTS = ("labassistant-ui", "labassistant-cli")

REQUIRED_SCOPES = {
    "list_experiments": HISTORY_READ,
    "retrieve_history_overview": HISTORY_READ,
    "retrieve_experiment": HISTORY_READ,
    "retrieve_related_context": MEMORY_READ,
    "retrieve_research_journal": MEMORY_READ,
}

DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True)
class LocalReadAccessContext:
    """Identity and scope assertions supplied by a trusted local host."""

    subject: str
    client_id: str
    origin: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class LocalReadAccessDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class LocalReadAccessPolicy:
    """Conservative local policy; it is not remote authentication."""

    allowed_clients: tuple[str, ...] = LOCAL_CLIENTS

    def evaluate(
        self,
        context: LocalReadAccessContext | None,
        capability: str,
    ) -> LocalReadAccessDecision:
        if not isinstance(context, LocalReadAccessContext):
            return LocalReadAccessDecision(False, "missing_context")
        if not isinstance(context.subject, str) or not context.subject.strip():
            return LocalReadAccessDecision(False, "missing_subject")
        if not isinstance(context.origin, str) or context.origin != "local":
            return LocalReadAccessDecision(False, "non_local_origin")
        if (
            not isinstance(context.client_id, str)
            or context.client_id not in self.allowed_clients
        ):
            return LocalReadAccessDecision(False, "unknown_client")
        if not isinstance(context.scopes, tuple) or not all(
            isinstance(scope, str) for scope in context.scopes
        ):
            return LocalReadAccessDecision(False, "invalid_scopes")
        required_scope = REQUIRED_SCOPES.get(capability)
        if required_scope and required_scope not in context.scopes:
            return LocalReadAccessDecision(False, "missing_scope")
        return LocalReadAccessDecision(True, "allowed")


@dataclass(frozen=True)
class PageMetadata:
    """Honest bounds for one ordered collection."""

    offset: int
    limit: int
    returned: int
    total: int | None
    has_more: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentListings:
    """Versioned list envelope without changing the existing tuple handler."""

    items: tuple[ExperimentListing, ...]
    pagination: PageMetadata
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "pagination": self.pagination.to_dict(),
            "api_version": self.api_version,
        }


@dataclass(frozen=True)
class APIError:
    """Stable draft error payload without internal exception details."""

    code: str
    message: str
    details: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class APISuccessEnvelope:
    api_version: str
    capability: str
    data: Any
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class APIErrorEnvelope:
    api_version: str
    capability: str
    error: APIError
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "capability": self.capability,
            "error": self.error.to_dict(),
            "ok": self.ok,
        }


APIEnvelope = APISuccessEnvelope | APIErrorEnvelope


def invoke_candidate_read(
    capability: str,
    parameters: dict[str, Any] | None = None,
    *,
    access_context: LocalReadAccessContext | None = None,
    access_policy: LocalReadAccessPolicy | None = None,
) -> APIEnvelope:
    """Invoke one audited draft read through a JSON-safe boundary.

    The context must be asserted by a trusted local host. The policy does not
    authenticate remote requests and must not be populated from request fields.
    """

    if not isinstance(capability, str):
        return _error("", INVALID_INPUT, "capability must be a string")
    if parameters is None:
        resolved_parameters = {}
    elif not isinstance(parameters, dict) or not all(
        isinstance(key, str) for key in parameters
    ):
        return _error(capability, INVALID_INPUT, "parameters must be an object")
    else:
        resolved_parameters = dict(parameters)
    if capability not in CANDIDATE_READS:
        return _error(
            capability,
            UNSUPPORTED_EVIDENCE,
            "Capability is not in the candidate read surface",
        )
    if capability in PROTECTED_READS:
        decision = (access_policy or LocalReadAccessPolicy()).evaluate(
            access_context,
            capability,
        )
        if not decision.allowed:
            return _error(
                capability,
                ACCESS_DENIED,
                "Local read policy denied access",
            )

    try:
        handler, arguments, bounds = _resolve_invocation(
            capability, resolved_parameters
        )
        result = handler(**arguments)
        if capability == "list_experiments":
            items, page = _page(tuple(result), **bounds)
            result = ExperimentListings(items=items, pagination=page)
        data = _bounded_data(capability, _serialize_result(result), bounds)
        json.dumps(data, allow_nan=False)
        return APISuccessEnvelope(
            api_version=AGENT_API_VERSION,
            capability=capability,
            data=data,
        )
    except ExperimentRecordNotFoundError:
        return _error(capability, NOT_FOUND, "Experiment record was not found")
    except ValueError as exc:
        return _error(capability, INVALID_INPUT, str(exc))
    except Exception:
        return _error(
            capability,
            INTERNAL_FAILURE,
            "The candidate read could not be completed",
        )


def _resolve_invocation(
    capability: str, parameters: dict[str, Any]
) -> tuple[Callable[..., Any], dict[str, Any], dict[str, int]]:
    handlers: dict[str, tuple[Callable[..., Any], frozenset[str]]] = {
        "describe_platform": (app_manifest, frozenset()),
        "describe_agent_access": (agent_access_policy, frozenset()),
        "list_experiments": (
            list_experiments,
            frozenset({"limit", "offset"}),
        ),
        "retrieve_history_overview": (
            retrieve_history_overview,
            frozenset({"limit", "offset"}),
        ),
        "retrieve_experiment": (retrieve_experiment, frozenset({"record_id"})),
        "retrieve_related_context": (
            retrieve_related_context,
            frozenset({"question", "tags", "limit"}),
        ),
        "retrieve_research_journal": (
            retrieve_research_journal,
            frozenset(
                {"keyword", "tag", "instrument", "sample", "limit", "offset"}
            ),
        ),
    }
    handler, allowed = handlers[capability]
    unexpected = sorted(set(parameters) - allowed)
    if unexpected:
        raise ValueError(f"Unsupported parameters: {', '.join(unexpected)}")

    arguments = dict(parameters)
    bounds: dict[str, int] = {}
    if capability in {
        "list_experiments",
        "retrieve_history_overview",
        "retrieve_research_journal",
    }:
        bounds = _pagination_arguments(arguments)
    if capability == "retrieve_experiment":
        record_id = arguments.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be a non-empty string")
    elif capability == "retrieve_related_context":
        question = arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        if "tags" in arguments:
            tags = arguments["tags"]
            if not isinstance(tags, (list, tuple)) or not all(
                isinstance(tag, str) for tag in tags
            ):
                raise ValueError("tags must contain only strings")
            arguments["tags"] = tuple(tags)
        if "limit" in arguments:
            limit = arguments["limit"]
            if (
                isinstance(limit, bool)
                or not isinstance(limit, int)
                or not 1 <= limit <= 50
            ):
                raise ValueError("limit must be an integer from 1 to 50")
        bounds = {"limit": arguments.get("limit", 6), "offset": 0}
    else:
        for key, value in arguments.items():
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")

    return handler, arguments, bounds


def _pagination_arguments(arguments: dict[str, Any]) -> dict[str, int]:
    limit = arguments.pop("limit", DEFAULT_PAGE_LIMIT)
    offset = arguments.pop("offset", 0)
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_PAGE_LIMIT
    ):
        raise ValueError(f"limit must be an integer from 1 to {MAX_PAGE_LIMIT}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    return {"limit": limit, "offset": offset}


def _page(
    values: tuple[Any, ...], *, limit: int, offset: int
) -> tuple[tuple[Any, ...], PageMetadata]:
    selected = values[offset : offset + limit]
    total = len(values)
    return selected, PageMetadata(
        offset=offset,
        limit=limit,
        returned=len(selected),
        total=total,
        has_more=offset + len(selected) < total,
    )


def _bounded_data(
    capability: str,
    data: Any,
    bounds: dict[str, int],
) -> Any:
    if capability == "retrieve_history_overview":
        payload = dict(data)
        pages = {}
        for key in ("summaries", "trend_points"):
            selected, page = _page(tuple(payload[key]), **bounds)
            payload[key] = list(selected)
            pages[key] = page.to_dict()
        payload["pagination"] = pages
        return payload
    if capability == "retrieve_research_journal":
        payload = dict(data)
        selected, page = _page(tuple(payload["entries"]), **bounds)
        payload["entries"] = list(selected)
        payload["markdown"] = _journal_page_markdown(payload, selected)
        payload["pagination"] = page.to_dict()
        return payload
    if capability == "retrieve_related_context":
        payload = dict(data)
        requested_limit = bounds["limit"]
        category_limits = {
            "relevant_experiments": 3,
            "relevant_observations": requested_limit,
            "supporting_evidence": requested_limit,
            "hypotheses": 3,
            "recommendations": 3,
            "related_notes": 3,
            "source_files": 5,
        }
        collections = {}
        for key, limit in category_limits.items():
            values = payload[key]
            collections[key] = PageMetadata(
                offset=0,
                limit=limit,
                returned=len(values),
                total=None,
                has_more=None,
            ).to_dict()
        for key in ("missing_information", "caveats"):
            values = payload[key]
            collections[key] = PageMetadata(
                offset=0,
                limit=len(values),
                returned=len(values),
                total=len(values),
                has_more=False,
            ).to_dict()
        payload["pagination"] = collections
        return payload
    return data


def _journal_page_markdown(payload: dict[str, Any], entries: tuple[Any, ...]) -> str:
    lines = ["# LabAssistant Research Journal", ""]
    filters = [
        f"{key}: {payload[key]}"
        for key in ("keyword", "tag", "instrument", "sample")
        if payload.get(key)
    ]
    if filters:
        lines.extend([f"_Filters: {', '.join(filters)}_", ""])
    if not entries:
        lines.append("_No journal entries matched this page._")
    else:
        for entry in entries:
            lines.extend(
                [
                    f"## {entry['title']}",
                    "",
                    f"- Date/time: {entry['created_at'] or 'unknown'}",
                    f"- Instrument: {entry['instrument'] or 'unknown'}",
                ]
            )
            for label, key in (
                ("Tags", "tags"),
                ("Samples", "samples"),
                ("Source files", "source_files"),
            ):
                if entry[key]:
                    lines.append(f"- {label}: {', '.join(entry[key])}")
            lines.append("")
            for label, key in (
                ("Key observations", "key_observations"),
                ("Hypotheses", "hypotheses"),
                ("Recommendations", "recommendations"),
                ("Notes", "notes"),
            ):
                if entry[key]:
                    lines.append(f"### {label}")
                    lines.extend(f"- {value}" for value in entry[key])
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _serialize_result(result: Any) -> Any:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    raise TypeError("Candidate read returned an unsupported result")


def _error(capability: str, code: str, message: str) -> APIErrorEnvelope:
    return APIErrorEnvelope(
        api_version=AGENT_API_VERSION,
        capability=capability,
        error=APIError(code=code, message=message),
    )
