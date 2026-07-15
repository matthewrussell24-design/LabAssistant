import os
from pathlib import Path
import socket
import tempfile
import threading

import pytest

import labassistant.local_read_client as client_api
import labassistant.local_read_transport as transport


def page(returned=0):
    return {"offset": 0, "limit": 25, "returned": returned, "total": returned, "has_more": False}


PAYLOADS = {
    "describe_platform": {
        "name": "LabAssistant",
        "direction": "Experiment Intelligence",
        "primary_surface": "desktop",
        "contract_version": "1.0",
        "contract_status": "stable",
        "capabilities": [
            {
                "name": "describe_platform",
                "purpose": "Describe platform",
                "access": "public",
                "required_scope": None,
                "request_parameters": [],
                "contract_version": "1.0",
            }
        ],
    },
    "describe_agent_access": {
        "contract_version": "1.0",
        "status": "local_read_only",
        "access_model": "host_asserted_local_policy",
        "public_capabilities": ["describe_platform"],
        "protected_capabilities": ["list_experiments"],
        "scopes": ["history:read", "memory:read"],
        "writes_allowed": False,
        "remote_authentication": False,
    },
    "list_experiments": {
        "items": [
            {
                "record_id": "record-1",
                "saved_at": "2026-07-15T00:00:00+00:00",
                "label": "Run 1",
                "measurement_count": 2,
            }
        ],
        "pagination": page(1),
    },
    "retrieve_history_overview": {
        "summaries": [{"record_id": "record-1"}],
        "trend_points": [{"label": "Run 1"}],
        "pagination": {"summaries": page(1), "trend_points": page(1)},
    },
    "retrieve_experiment": {
        "record_id": "record-1",
        "saved_at": "2026-07-15T00:00:00+00:00",
        "label": "Run 1",
        "measurement_count": 2,
    },
    "retrieve_related_context": {
        "question": "What changed?",
        "relevant_experiments": [],
        "relevant_observations": [{"label": "shift"}],
        "supporting_evidence": [],
        "hypotheses": [],
        "recommendations": [],
        "related_notes": [],
        "source_files": [],
        "missing_information": [],
        "confidence": "Low",
        "caveats": [],
        "pagination": {
            key: page(0)
            for key in (
                "relevant_experiments",
                "relevant_observations",
                "supporting_evidence",
                "hypotheses",
                "recommendations",
                "related_notes",
                "source_files",
                "missing_information",
                "caveats",
            )
        },
    },
    "retrieve_research_journal": {
        "keyword": "aggregation",
        "tag": "dls",
        "instrument": "",
        "sample": "",
        "entries": [{"entry_id": "entry-1", "notes": ["review"]}],
        "markdown": "# Research Journal\n",
        "pagination": page(1),
    },
}


def success_requester(calls):
    def requester(capability, parameters, *, socket_path, request_id):
        calls.append((capability, parameters, socket_path, request_id))
        return {
            "transport_version": "1",
            "request_id": request_id,
            "response": {
                "api_version": "1.0",
                "capability": capability,
                "data": PAYLOADS[capability],
                "ok": True,
            },
        }

    return requester


def test_all_seven_methods_return_typed_immutable_results():
    calls = []
    client = client_api.LocalReadClient("/tmp/read.sock", requester=success_requester(calls))
    results = (
        client.describe_platform(),
        client.describe_agent_access(),
        client.list_experiments(limit=10, offset=2),
        client.retrieve_history_overview(limit=5),
        client.retrieve_experiment("record-1"),
        client.retrieve_related_context("What changed?", tags=("dls",), limit=3),
        client.retrieve_research_journal(keyword="aggregation", tag="dls"),
    )

    assert tuple(result.capability for result in results) == tuple(PAYLOADS)
    assert isinstance(results[0].data, client_api.PlatformDescription)
    assert isinstance(results[1].data, client_api.AgentAccessDescription)
    assert isinstance(results[2].data, client_api.ExperimentPage)
    assert isinstance(results[3].data, client_api.HistoryOverview)
    assert isinstance(results[4].data, client_api.RetrievedExperiment)
    assert isinstance(results[5].data, client_api.RelatedContext)
    assert isinstance(results[6].data, client_api.ResearchJournal)
    assert results[2].data.items[0].measurement_count == 2
    assert results[2].data.pagination.returned == 1
    with pytest.raises(TypeError):
        results[3].data.summaries[0]["record_id"] = "changed"
    assert all(call[2] == Path("/tmp/read.sock") for call in calls)
    assert len({call[3] for call in calls}) == 7
    assert calls[2][1] == {"limit": 10, "offset": 2}
    assert calls[5][1]["tags"] == ["dls"]


def test_transport_application_protocol_and_connection_failures_are_distinct():
    def transport_failure(capability, parameters, *, socket_path, request_id):
        return {
            "transport_version": "1",
            "request_id": request_id,
            "error": {"code": "peer_denied", "message": "denied"},
        }

    with pytest.raises(client_api.LocalReadTransportError) as caught:
        client_api.LocalReadClient(requester=transport_failure).describe_platform()
    assert caught.value.code == "peer_denied"

    def application_failure(capability, parameters, *, socket_path, request_id):
        return {
            "transport_version": "1",
            "request_id": request_id,
            "response": {
                "api_version": "1.0",
                "capability": capability,
                "ok": False,
                "error": {
                    "code": "not_found",
                    "message": "missing",
                    "details": {"safe": True},
                },
            },
        }

    with pytest.raises(client_api.LocalReadApplicationError) as caught:
        client_api.LocalReadClient(requester=application_failure).retrieve_experiment("missing")
    assert caught.value.code == "not_found"
    assert caught.value.capability == "retrieve_experiment"
    assert caught.value.details["safe"] is True

    def malformed(capability, parameters, *, socket_path, request_id):
        return {"transport_version": "1", "request_id": "wrong", "response": {}}

    with pytest.raises(client_api.LocalReadProtocolError):
        client_api.LocalReadClient(requester=malformed).describe_platform()

    def disconnected(*args, **kwargs):
        raise FileNotFoundError("private socket path")

    with pytest.raises(client_api.LocalReadConnectionError) as caught:
        client_api.LocalReadClient(requester=disconnected).describe_platform()
    assert "private socket path" not in str(caught.value)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda frame: frame.update(transport_version="2"),
        lambda frame: frame.update(request_id="wrong"),
        lambda frame: frame["response"].update(api_version="2.0"),
        lambda frame: frame["response"].update(capability="describe_agent_access"),
        lambda frame: frame["response"].update(data={"name": 3}),
    ),
)
def test_protocol_validation_rejects_incompatible_or_malformed_success(mutation):
    def requester(capability, parameters, *, socket_path, request_id):
        frame = {
            "transport_version": "1",
            "request_id": request_id,
            "response": {
                "api_version": "1.0",
                "capability": capability,
                "data": dict(PAYLOADS[capability]),
                "ok": True,
            },
        }
        mutation(frame)
        return frame

    with pytest.raises(client_api.LocalReadProtocolError):
        client_api.LocalReadClient(requester=requester).describe_platform()


def test_client_compatibility_with_real_foreground_broker():
    runtime = Path(tempfile.mkdtemp(prefix="la-client-", dir="/tmp"))
    runtime.chmod(0o700)
    socket_path = runtime / "read.sock"
    owner = transport.PeerCredentials(uid=os.getuid(), gid=os.getgid())
    broker = transport.LocalReadBroker(
        socket_path, credential_resolver=lambda _: owner
    )
    broker.start()
    try:
        for method in (
            client_api.LocalReadClient(socket_path).describe_platform,
            client_api.LocalReadClient(socket_path).describe_agent_access,
            client_api.LocalReadClient(socket_path).list_experiments,
        ):
            worker = threading.Thread(target=broker.serve_once)
            worker.start()
            result = method()
            worker.join(timeout=2)
            assert not worker.is_alive()
            assert result.api_version == "1.0"
    finally:
        broker.close()
        for child in runtime.iterdir():
            child.unlink()
        runtime.rmdir()
