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


@dataclass(frozen=True)
class ExperimentListings:
    """Versioned list envelope without changing the existing tuple handler."""

    items: tuple[ExperimentListing, ...]
    api_version: str = AGENT_API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
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
    access_granted: bool = False,
) -> APIEnvelope:
    """Invoke one audited draft read through a JSON-safe boundary.

    ``access_granted`` is a trusted adapter decision, not a request parameter or
    an authorization mechanism. A future transport must derive it from its own
    local access policy.
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
    if capability in PROTECTED_READS and access_granted is not True:
        return _error(
            capability,
            ACCESS_DENIED,
            "A trusted read-access decision is required",
        )

    try:
        handler, arguments = _resolve_invocation(capability, resolved_parameters)
        result = handler(**arguments)
        if capability == "list_experiments":
            result = ExperimentListings(items=tuple(result))
        data = _serialize_result(result)
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
) -> tuple[Callable[..., Any], dict[str, Any]]:
    handlers: dict[str, tuple[Callable[..., Any], frozenset[str]]] = {
        "describe_platform": (app_manifest, frozenset()),
        "describe_agent_access": (agent_access_policy, frozenset()),
        "list_experiments": (list_experiments, frozenset()),
        "retrieve_history_overview": (retrieve_history_overview, frozenset()),
        "retrieve_experiment": (retrieve_experiment, frozenset({"record_id"})),
        "retrieve_related_context": (
            retrieve_related_context,
            frozenset({"question", "tags", "limit"}),
        ),
        "retrieve_research_journal": (
            retrieve_research_journal,
            frozenset({"keyword", "tag", "instrument", "sample"}),
        ),
    }
    handler, allowed = handlers[capability]
    unexpected = sorted(set(parameters) - allowed)
    if unexpected:
        raise ValueError(f"Unsupported parameters: {', '.join(unexpected)}")

    arguments = dict(parameters)
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
    else:
        for key, value in arguments.items():
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")

    return handler, arguments


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
