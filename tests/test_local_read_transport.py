import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import threading

import pytest

import labassistant.local_read_transport as transport
from labassistant.api_readiness import CANDIDATE_READS


OWNER = transport.PeerCredentials(uid=os.getuid(), gid=os.getgid())


@pytest.fixture
def short_socket_path():
    runtime = Path(tempfile.mkdtemp(prefix="la-read-", dir="/tmp"))
    runtime.chmod(0o700)
    try:
        yield runtime / "read.sock"
    finally:
        for child in runtime.iterdir():
            child.unlink()
        runtime.rmdir()


def request_frame(capability="describe_platform", **overrides):
    frame = {
        "transport_version": transport.TRANSPORT_VERSION,
        "request_id": "request-1",
        "contract_version": "1.0",
        "capability": capability,
        "parameters": {},
    }
    frame.update(overrides)
    return frame


def exchange(broker, payload):
    server, client = socket.socketpair()
    try:
        client.sendall(payload + b"\n")
        return json.loads(broker._handle_connection(server))
    finally:
        server.close()
        client.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS credential gate")
def test_peer_credentials_resolve_real_same_user_socket_pair():
    server, client = socket.socketpair()
    try:
        peer = transport.get_peer_credentials(server)
    finally:
        server.close()
        client.close()
    assert peer == OWNER


def test_request_parser_enforces_versions_allowlist_and_no_identity_fields():
    parsed = transport.parse_request(json.dumps(request_frame()).encode())
    assert parsed["capability"] == "describe_platform"

    rejected = (
        request_frame(transport_version="2"),
        request_frame(contract_version="0.1-draft"),
        request_frame(capability="save_experiment_history"),
        request_frame(subject="uid:0"),
        request_frame(parameters=[]),
    )
    for frame in rejected:
        with pytest.raises(ValueError):
            transport.parse_request(json.dumps(frame).encode())
    with pytest.raises(ValueError, match="malformed_json"):
        transport.parse_request(b"not json")
    with pytest.raises(ValueError, match="request_size"):
        transport.parse_request(b"x" * (transport.MAX_REQUEST_BYTES + 1))


def test_broker_derives_access_context_and_preserves_application_envelope(
    tmp_path, monkeypatch
):
    calls = []

    class Result:
        def to_dict(self):
            return {
                "api_version": "1.0",
                "capability": "list_experiments",
                "data": {"items": []},
                "ok": True,
            }

    def invoke(capability, parameters, *, access_context):
        calls.append((capability, parameters, access_context))
        return Result()

    monkeypatch.setattr(transport, "invoke_candidate_read", invoke)
    broker = transport.LocalReadBroker(
        tmp_path / "runtime" / "read.sock", credential_resolver=lambda _: OWNER
    )
    payload = json.dumps(request_frame("list_experiments")).encode()
    response = exchange(broker, payload)

    assert response["request_id"] == "request-1"
    assert response["response"]["api_version"] == "1.0"
    capability, parameters, context = calls[0]
    assert capability == "list_experiments"
    assert parameters == {}
    assert context.subject == f"uid:{os.getuid()}"
    assert context.client_id == transport.BROKER_CLIENT_ID
    assert context.origin == "local"
    assert context.scopes == ("history:read", "memory:read")


def test_broker_fails_closed_for_unverified_or_other_user_peer(tmp_path):
    unverified = transport.LocalReadBroker(
        tmp_path / "one.sock",
        credential_resolver=lambda _: (_ for _ in ()).throw(
            transport.TransportUnavailableError()
        ),
    )
    response = exchange(unverified, json.dumps(request_frame()).encode())
    assert response["error"]["code"] == "peer_unverified"

    other_user = transport.LocalReadBroker(
        tmp_path / "two.sock",
        credential_resolver=lambda _: transport.PeerCredentials(
            uid=os.getuid() + 1, gid=os.getgid()
        ),
    )
    response = exchange(other_user, json.dumps(request_frame()).encode())
    assert response["error"]["code"] == "peer_denied"


def test_broker_reports_generic_transport_errors_without_request_details(tmp_path):
    broker = transport.LocalReadBroker(
        tmp_path / "read.sock", credential_resolver=lambda _: OWNER
    )
    response = exchange(broker, b'{"secret":"/private/path"}')
    assert response["error"]["code"] == "invalid_frame"
    assert "secret" not in json.dumps(response)
    assert "/private/path" not in json.dumps(response)


def test_valid_request_preserves_stable_application_error(tmp_path):
    broker = transport.LocalReadBroker(
        tmp_path / "read.sock", credential_resolver=lambda _: OWNER
    )
    payload = json.dumps(
        request_frame("retrieve_experiment", parameters={"record_id": ""})
    ).encode()
    response = exchange(broker, payload)
    assert response["request_id"] == "request-1"
    assert response["response"]["api_version"] == "1.0"
    assert response["response"]["error"]["code"] == "invalid_input"


def test_socket_lifecycle_modes_active_refusal_and_cleanup(short_socket_path):
    socket_path = short_socket_path
    broker = transport.LocalReadBroker(
        socket_path, credential_resolver=lambda _: OWNER
    )
    broker.start()
    try:
        assert stat.S_IMODE(socket_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(socket_path.stat().st_mode) == 0o600
        with pytest.raises(transport.UnsafeSocketPathError, match="already running"):
            transport.LocalReadBroker(socket_path).start()
    finally:
        broker.close()
    assert not socket_path.exists()


def test_stale_socket_is_removed_but_regular_file_is_never_unlinked(short_socket_path):
    socket_path = short_socket_path
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()

    broker = transport.LocalReadBroker(
        socket_path, credential_resolver=lambda _: OWNER
    )
    broker.start()
    broker.close()
    assert not socket_path.exists()

    socket_path.write_text("do not remove")
    with pytest.raises(transport.UnsafeSocketPathError):
        transport.LocalReadBroker(socket_path).start()
    assert socket_path.read_text() == "do not remove"


def test_diagnostic_client_round_trips_every_public_read(short_socket_path, monkeypatch):
    socket_path = short_socket_path
    seen = []

    class Result:
        def __init__(self, capability):
            self.capability = capability

        def to_dict(self):
            return {
                "api_version": "1.0",
                "capability": self.capability,
                "data": {},
                "ok": True,
            }

    def invoke(capability, parameters, *, access_context):
        seen.append(capability)
        return Result(capability)

    monkeypatch.setattr(transport, "invoke_candidate_read", invoke)
    broker = transport.LocalReadBroker(
        socket_path, credential_resolver=lambda _: OWNER
    )
    broker.start()
    try:
        for capability in CANDIDATE_READS:
            worker = threading.Thread(target=broker.serve_once)
            worker.start()
            response = transport.request_read(capability, socket_path=socket_path)
            worker.join(timeout=2)
            assert not worker.is_alive()
            assert response["response"]["capability"] == capability
    finally:
        broker.close()
    assert tuple(seen) == CANDIDATE_READS


def test_runtime_directory_must_be_owner_only(short_socket_path):
    runtime = short_socket_path.parent
    runtime.chmod(0o755)
    broker = transport.LocalReadBroker(runtime / "read.sock")
    with pytest.raises(transport.UnsafeSocketPathError, match="owner-only"):
        broker.start()


def test_socket_path_length_fails_before_bind(tmp_path):
    socket_path = tmp_path / ("x" * transport.MAX_SOCKET_PATH_BYTES)
    with pytest.raises(transport.UnsafeSocketPathError, match="platform limit"):
        transport.LocalReadBroker(socket_path).start()
