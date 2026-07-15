"""Typed client SDK for LabAssistant's stable local read-only broker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Generic, Mapping, TypeVar
from uuid import uuid4

from labassistant.api_readiness import PUBLIC_READ_CONTRACT_VERSION
from labassistant.local_read_transport import request_read


JSONMapping = Mapping[str, Any]
PayloadT = TypeVar("PayloadT")
Requester = Callable[..., dict[str, Any]]


class LocalReadClientError(RuntimeError):
    """Base class for typed local client failures."""


class LocalReadConnectionError(LocalReadClientError):
    """The client could not complete a request through the local transport."""


class LocalReadProtocolError(LocalReadClientError):
    """The broker response did not match the selected transport/contract."""


class LocalReadTransportError(LocalReadClientError):
    """The broker rejected a request before application invocation."""

    def __init__(self, code: str, message: str, request_id: str | None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


class LocalReadApplicationError(LocalReadClientError):
    """A stable application error returned inside a valid transport response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        capability: str,
        api_version: str,
        details: JSONMapping,
        request_id: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.capability = capability
        self.api_version = api_version
        self.details = _freeze_mapping(details)
        self.request_id = request_id


@dataclass(frozen=True)
class LocalReadResult(Generic[PayloadT]):
    request_id: str
    api_version: str
    capability: str
    data: PayloadT


@dataclass(frozen=True)
class Pagination:
    offset: int
    limit: int
    returned: int
    total: int | None
    has_more: bool | None


@dataclass(frozen=True)
class PublicReadCapability:
    name: str
    purpose: str
    access: str
    required_scope: str | None
    request_parameters: tuple[str, ...]
    contract_version: str


@dataclass(frozen=True)
class PlatformDescription:
    name: str
    direction: str
    primary_surface: str
    contract_version: str
    contract_status: str
    capabilities: tuple[PublicReadCapability, ...]


@dataclass(frozen=True)
class AgentAccessDescription:
    contract_version: str
    status: str
    access_model: str
    public_capabilities: tuple[str, ...]
    protected_capabilities: tuple[str, ...]
    scopes: tuple[str, ...]
    writes_allowed: bool
    remote_authentication: bool


@dataclass(frozen=True)
class ExperimentListing:
    record_id: str
    saved_at: str
    label: str
    measurement_count: int


@dataclass(frozen=True)
class ExperimentPage:
    items: tuple[ExperimentListing, ...]
    pagination: Pagination


@dataclass(frozen=True)
class HistoryOverview:
    summaries: tuple[JSONMapping, ...]
    trend_points: tuple[JSONMapping, ...]
    pagination: Mapping[str, Pagination]


@dataclass(frozen=True)
class RetrievedExperiment:
    record_id: str
    saved_at: str
    label: str
    measurement_count: int


@dataclass(frozen=True)
class RelatedContext:
    question: str
    relevant_experiments: tuple[Any, ...]
    relevant_observations: tuple[Any, ...]
    supporting_evidence: tuple[Any, ...]
    hypotheses: tuple[Any, ...]
    recommendations: tuple[Any, ...]
    related_notes: tuple[Any, ...]
    source_files: tuple[Any, ...]
    missing_information: tuple[Any, ...]
    confidence: str
    caveats: tuple[Any, ...]
    pagination: Mapping[str, Pagination]


@dataclass(frozen=True)
class ResearchJournal:
    keyword: str
    tag: str
    instrument: str
    sample: str
    entries: tuple[JSONMapping, ...]
    markdown: str
    pagination: Pagination


class LocalReadClient:
    """Capability-specific, read-only client for a running local broker."""

    def __init__(
        self,
        socket_path: Path | str | None = None,
        *,
        requester: Requester = request_read,
    ) -> None:
        self.socket_path = Path(socket_path) if socket_path else None
        self._requester = requester

    def describe_platform(self) -> LocalReadResult[PlatformDescription]:
        return self._invoke("describe_platform", {}, _platform)

    def describe_agent_access(self) -> LocalReadResult[AgentAccessDescription]:
        return self._invoke("describe_agent_access", {}, _agent_access)

    def list_experiments(
        self, *, limit: int = 25, offset: int = 0
    ) -> LocalReadResult[ExperimentPage]:
        return self._invoke(
            "list_experiments", {"limit": limit, "offset": offset}, _experiment_page
        )

    def retrieve_history_overview(
        self, *, limit: int = 25, offset: int = 0
    ) -> LocalReadResult[HistoryOverview]:
        return self._invoke(
            "retrieve_history_overview",
            {"limit": limit, "offset": offset},
            _history_overview,
        )

    def retrieve_experiment(
        self, record_id: str
    ) -> LocalReadResult[RetrievedExperiment]:
        return self._invoke(
            "retrieve_experiment", {"record_id": record_id}, _retrieved_experiment
        )

    def retrieve_related_context(
        self,
        question: str,
        *,
        tags: tuple[str, ...] | list[str] = (),
        limit: int = 6,
    ) -> LocalReadResult[RelatedContext]:
        return self._invoke(
            "retrieve_related_context",
            {"question": question, "tags": list(tags), "limit": limit},
            _related_context,
        )

    def retrieve_research_journal(
        self,
        *,
        keyword: str = "",
        tag: str = "",
        instrument: str = "",
        sample: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> LocalReadResult[ResearchJournal]:
        return self._invoke(
            "retrieve_research_journal",
            {
                "keyword": keyword,
                "tag": tag,
                "instrument": instrument,
                "sample": sample,
                "limit": limit,
                "offset": offset,
            },
            _research_journal,
        )

    def _invoke(
        self,
        capability: str,
        parameters: dict[str, Any],
        decoder: Callable[[JSONMapping], PayloadT],
    ) -> LocalReadResult[PayloadT]:
        request_id = uuid4().hex
        try:
            frame = self._requester(
                capability,
                parameters,
                socket_path=self.socket_path,
                request_id=request_id,
            )
        except LocalReadClientError:
            raise
        except Exception as exc:
            raise LocalReadConnectionError("Local read broker request failed") from exc
        return _decode_frame(frame, request_id, capability, decoder)


def _decode_frame(
    frame: object,
    request_id: str,
    capability: str,
    decoder: Callable[[JSONMapping], PayloadT],
) -> LocalReadResult[PayloadT]:
    if not isinstance(frame, dict):
        raise LocalReadProtocolError("Broker response must be an object")
    if frame.get("transport_version") != "1":
        raise LocalReadProtocolError("Broker transport version is incompatible")
    response_request_id = frame.get("request_id")
    error = frame.get("error")
    if isinstance(error, dict):
        raise LocalReadTransportError(
            _string(error, "code"),
            _string(error, "message"),
            response_request_id if isinstance(response_request_id, str) else None,
        )
    if response_request_id != request_id:
        raise LocalReadProtocolError("Broker response request ID did not match")
    envelope = frame.get("response")
    if not isinstance(envelope, dict):
        raise LocalReadProtocolError("Broker response envelope was missing")
    api_version = _string(envelope, "api_version")
    if api_version != PUBLIC_READ_CONTRACT_VERSION:
        raise LocalReadProtocolError("Application contract version is incompatible")
    if envelope.get("capability") != capability:
        raise LocalReadProtocolError("Application capability did not match request")
    if envelope.get("ok") is False:
        application_error = envelope.get("error")
        if not isinstance(application_error, dict):
            raise LocalReadProtocolError("Application error payload was missing")
        details = application_error.get("details", {})
        if not isinstance(details, dict):
            raise LocalReadProtocolError("Application error details were invalid")
        raise LocalReadApplicationError(
            _string(application_error, "code"),
            _string(application_error, "message"),
            capability=capability,
            api_version=api_version,
            details=details,
            request_id=request_id,
        )
    if envelope.get("ok") is not True or not isinstance(envelope.get("data"), dict):
        raise LocalReadProtocolError("Application success payload was invalid")
    try:
        data = decoder(envelope["data"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LocalReadProtocolError("Application data shape was invalid") from exc
    return LocalReadResult(request_id, api_version, capability, data)


def _platform(data: JSONMapping) -> PlatformDescription:
    capabilities = tuple(
        PublicReadCapability(
            name=_string(item, "name"),
            purpose=_string(item, "purpose"),
            access=_string(item, "access"),
            required_scope=_optional_string(item, "required_scope"),
            request_parameters=_strings(item, "request_parameters"),
            contract_version=_string(item, "contract_version"),
        )
        for item in _mappings(data, "capabilities")
    )
    return PlatformDescription(
        name=_string(data, "name"),
        direction=_string(data, "direction"),
        primary_surface=_string(data, "primary_surface"),
        contract_version=_string(data, "contract_version"),
        contract_status=_string(data, "contract_status"),
        capabilities=capabilities,
    )


def _agent_access(data: JSONMapping) -> AgentAccessDescription:
    return AgentAccessDescription(
        contract_version=_string(data, "contract_version"),
        status=_string(data, "status"),
        access_model=_string(data, "access_model"),
        public_capabilities=_strings(data, "public_capabilities"),
        protected_capabilities=_strings(data, "protected_capabilities"),
        scopes=_strings(data, "scopes"),
        writes_allowed=_boolean(data, "writes_allowed"),
        remote_authentication=_boolean(data, "remote_authentication"),
    )


def _pagination(data: JSONMapping) -> Pagination:
    return Pagination(
        offset=_integer(data, "offset"),
        limit=_integer(data, "limit"),
        returned=_integer(data, "returned"),
        total=_optional_integer(data, "total"),
        has_more=_optional_boolean(data, "has_more"),
    )


def _experiment_page(data: JSONMapping) -> ExperimentPage:
    return ExperimentPage(
        items=tuple(
            ExperimentListing(
                record_id=_string(item, "record_id"),
                saved_at=_string(item, "saved_at"),
                label=_string(item, "label"),
                measurement_count=_integer(item, "measurement_count"),
            )
            for item in _mappings(data, "items")
        ),
        pagination=_pagination(_mapping(data, "pagination")),
    )


def _history_overview(data: JSONMapping) -> HistoryOverview:
    pages = _mapping(data, "pagination")
    return HistoryOverview(
        summaries=tuple(_freeze_mapping(item) for item in _mappings(data, "summaries")),
        trend_points=tuple(
            _freeze_mapping(item) for item in _mappings(data, "trend_points")
        ),
        pagination=_pagination_map(pages, ("summaries", "trend_points")),
    )


def _retrieved_experiment(data: JSONMapping) -> RetrievedExperiment:
    return RetrievedExperiment(
        record_id=_string(data, "record_id"),
        saved_at=_string(data, "saved_at"),
        label=_string(data, "label"),
        measurement_count=_integer(data, "measurement_count"),
    )


def _related_context(data: JSONMapping) -> RelatedContext:
    pages = _mapping(data, "pagination")
    return RelatedContext(
        question=_string(data, "question"),
        relevant_experiments=_frozen_values(data, "relevant_experiments"),
        relevant_observations=_frozen_values(data, "relevant_observations"),
        supporting_evidence=_frozen_values(data, "supporting_evidence"),
        hypotheses=_frozen_values(data, "hypotheses"),
        recommendations=_frozen_values(data, "recommendations"),
        related_notes=_frozen_values(data, "related_notes"),
        source_files=_frozen_values(data, "source_files"),
        missing_information=_frozen_values(data, "missing_information"),
        confidence=_string(data, "confidence"),
        caveats=_frozen_values(data, "caveats"),
        pagination=_pagination_map(
            pages,
            (
                "relevant_experiments",
                "relevant_observations",
                "supporting_evidence",
                "hypotheses",
                "recommendations",
                "related_notes",
                "source_files",
                "missing_information",
                "caveats",
            ),
        ),
    )


def _research_journal(data: JSONMapping) -> ResearchJournal:
    return ResearchJournal(
        keyword=_string(data, "keyword"),
        tag=_string(data, "tag"),
        instrument=_string(data, "instrument"),
        sample=_string(data, "sample"),
        entries=tuple(_freeze_mapping(item) for item in _mappings(data, "entries")),
        markdown=_string(data, "markdown"),
        pagination=_pagination(_mapping(data, "pagination")),
    )


def _mapping(data: JSONMapping, key: str) -> dict[str, Any]:
    value = data[key]
    if not isinstance(value, dict):
        raise TypeError(key)
    return value


def _mappings(data: JSONMapping, key: str) -> tuple[dict[str, Any], ...]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(key)
    return tuple(value)


def _string(data: JSONMapping, key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(key)
    return value


def _optional_string(data: JSONMapping, key: str) -> str | None:
    value = data[key]
    if value is not None and not isinstance(value, str):
        raise TypeError(key)
    return value


def _strings(data: JSONMapping, key: str) -> tuple[str, ...]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(key)
    return tuple(value)


def _integer(data: JSONMapping, key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(key)
    return value


def _optional_integer(data: JSONMapping, key: str) -> int | None:
    value = data[key]
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(key)
    return value


def _boolean(data: JSONMapping, key: str) -> bool:
    value = data[key]
    if not isinstance(value, bool):
        raise TypeError(key)
    return value


def _optional_boolean(data: JSONMapping, key: str) -> bool | None:
    value = data[key]
    if value is not None and not isinstance(value, bool):
        raise TypeError(key)
    return value


def _frozen_values(data: JSONMapping, key: str) -> tuple[Any, ...]:
    value = data[key]
    if not isinstance(value, list):
        raise TypeError(key)
    return tuple(_freeze(item) for item in value)


def _freeze_mapping(value: JSONMapping) -> JSONMapping:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _pagination_map(
    values: JSONMapping, required_keys: tuple[str, ...]
) -> Mapping[str, Pagination]:
    pages = {}
    for key in required_keys:
        value = values[key]
        if not isinstance(value, dict):
            raise TypeError(key)
        pages[key] = _pagination(value)
    return MappingProxyType(pages)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
