"""Bounded owner-only Unix-domain transport for the stable read contract."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
from dataclasses import dataclass
import json
import os
from pathlib import Path
import socket
import stat
import sys
import threading
from typing import Any, Callable

from labassistant.api_readiness import (
    CANDIDATE_READS,
    HISTORY_READ,
    MEMORY_READ,
    PUBLIC_READ_CONTRACT_VERSION,
    LocalReadAccessContext,
    invoke_candidate_read,
)
from labassistant.runtime_paths import resolve_runtime_paths


TRANSPORT_VERSION = "1"
BROKER_CLIENT_ID = "labassistant-local-broker"
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
SOCKET_TIMEOUT_SECONDS = 5.0
LISTEN_BACKLOG = 8
MAX_SOCKET_PATH_BYTES = 103
ALLOWED_REQUEST_FIELDS = frozenset(
    {
        "transport_version",
        "request_id",
        "contract_version",
        "capability",
        "parameters",
    }
)


class TransportUnavailableError(RuntimeError):
    """Raised when the platform cannot establish the required local boundary."""


class UnsafeSocketPathError(RuntimeError):
    """Raised when a socket or runtime path cannot be managed safely."""


class BrokerAlreadyRunningError(UnsafeSocketPathError):
    """Raised when a live broker already owns the requested socket."""


@dataclass(frozen=True)
class PeerCredentials:
    uid: int
    gid: int


def default_socket_path() -> Path:
    """Return the per-user default without creating filesystem state."""
    return resolve_runtime_paths().socket_path


def get_peer_credentials(connection: socket.socket) -> PeerCredentials:
    """Resolve a connected peer through macOS getpeereid, or fail closed."""
    if sys.platform != "darwin":
        raise TransportUnavailableError("peer credentials are unavailable")
    library = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
    try:
        getpeereid = library.getpeereid
    except AttributeError as exc:
        raise TransportUnavailableError("peer credentials are unavailable") from exc
    getpeereid.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint),
    ]
    getpeereid.restype = ctypes.c_int
    uid = ctypes.c_uint()
    gid = ctypes.c_uint()
    if getpeereid(connection.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
        raise TransportUnavailableError("peer credentials could not be verified")
    return PeerCredentials(uid=uid.value, gid=gid.value)


def transport_error(
    code: str, message: str, request_id: str | None = None
) -> dict[str, Any]:
    return {
        "transport_version": TRANSPORT_VERSION,
        "request_id": request_id,
        "error": {"code": code, "message": message},
    }


def parse_request(payload: bytes) -> dict[str, Any]:
    """Validate one complete request line and return its typed JSON object."""
    if not payload or len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("request_size")
    try:
        request = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed_json") from exc
    if not isinstance(request, dict):
        raise ValueError("invalid_frame")
    if set(request) - ALLOWED_REQUEST_FIELDS:
        raise ValueError("invalid_frame")
    if request.get("transport_version") != TRANSPORT_VERSION:
        raise ValueError("unsupported_transport_version")
    if request.get("contract_version") != PUBLIC_READ_CONTRACT_VERSION:
        raise ValueError("unsupported_contract_version")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise ValueError("invalid_request_id")
    capability = request.get("capability")
    if not isinstance(capability, str) or capability not in CANDIDATE_READS:
        raise ValueError("unsupported_capability")
    parameters = request.get("parameters", {})
    if not isinstance(parameters, dict) or not all(
        isinstance(key, str) for key in parameters
    ):
        raise ValueError("invalid_parameters")
    return request


def encode_frame(frame: dict[str, Any]) -> bytes:
    encoded = json.dumps(
        frame, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8") + b"\n"
    if len(encoded) > MAX_RESPONSE_BYTES:
        encoded = json.dumps(
            transport_error("response_too_large", "Response exceeded transport limit"),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n"
    return encoded


class LocalReadBroker:
    """Foreground single-process broker for the stable read-only allowlist."""

    def __init__(
        self,
        socket_path: Path | str | None = None,
        *,
        credential_resolver: Callable[[socket.socket], PeerCredentials] = get_peer_credentials,
    ) -> None:
        self.socket_path = Path(socket_path) if socket_path else default_socket_path()
        self.credential_resolver = credential_resolver
        self._listener: socket.socket | None = None

    def start(self) -> None:
        if len(os.fsencode(self.socket_path)) > MAX_SOCKET_PATH_BYTES:
            raise UnsafeSocketPathError("socket path exceeds platform limit")
        self._prepare_runtime_directory()
        self._remove_stale_socket()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            listener.listen(LISTEN_BACKLOG)
            self._listener = listener
        except Exception:
            listener.close()
            self._unlink_owned_socket()
            raise

    def close(self) -> None:
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        self._unlink_owned_socket()

    def serve_once(self) -> None:
        listener = self._listener
        if listener is None:
            raise RuntimeError("broker is not started")
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(SOCKET_TIMEOUT_SECONDS)
            response = self._handle_connection(connection)
            try:
                connection.sendall(response)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def serve_forever(self) -> None:
        self.start()
        stop_event = threading.Event()
        try:
            self.serve_until(stop_event)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def serve_until(
        self,
        stop_event: threading.Event,
        *,
        poll_interval: float = 0.2,
    ) -> None:
        """Serve an already-started broker until cooperative stop is requested."""
        listener = self._listener
        if listener is None:
            raise RuntimeError("broker is not started")
        listener.settimeout(poll_interval)
        while not stop_event.is_set():
            try:
                self.serve_once()
            except socket.timeout:
                continue
            except OSError:
                if stop_event.is_set() or self._listener is None:
                    return
                raise

    def _handle_connection(self, connection: socket.socket) -> bytes:
        try:
            peer = self.credential_resolver(connection)
            if peer.uid != os.getuid():
                return encode_frame(
                    transport_error("peer_denied", "Peer is not the broker owner")
                )
        except Exception:
            return encode_frame(
                transport_error("peer_unverified", "Peer identity could not be verified")
            )

        payload = _read_request_line(connection)
        try:
            request = parse_request(payload)
        except ValueError as exc:
            code = str(exc)
            message = {
                "request_size": "Request exceeded transport limit",
                "malformed_json": "Request was not valid UTF-8 JSON",
                "unsupported_transport_version": "Transport version is unsupported",
                "unsupported_contract_version": "Contract version is unsupported",
                "unsupported_capability": "Capability is not in the public read surface",
            }.get(code, "Request frame was invalid")
            return encode_frame(transport_error(code, message))

        access_context = LocalReadAccessContext(
            subject=f"uid:{peer.uid}",
            client_id=BROKER_CLIENT_ID,
            origin="local",
            scopes=(HISTORY_READ, MEMORY_READ),
        )
        response = invoke_candidate_read(
            request["capability"],
            request.get("parameters", {}),
            access_context=access_context,
        ).to_dict()
        return encode_frame(
            {
                "transport_version": TRANSPORT_VERSION,
                "request_id": request["request_id"],
                "response": response,
            }
        )

    def _prepare_runtime_directory(self) -> None:
        directory = self.socket_path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise UnsafeSocketPathError("runtime directory must be owner-only")

    def _remove_stale_socket(self) -> None:
        try:
            info = self.socket_path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise UnsafeSocketPathError("existing socket path is unsafe")
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.2)
            probe.connect(str(self.socket_path))
        except (ConnectionRefusedError, FileNotFoundError):
            self.socket_path.unlink(missing_ok=True)
        else:
            raise BrokerAlreadyRunningError("read broker is already running")
        finally:
            probe.close()

    def _unlink_owned_socket(self) -> None:
        try:
            info = self.socket_path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid():
            self.socket_path.unlink()


def _read_request_line(connection: socket.socket) -> bytes:
    payload = bytearray()
    while len(payload) <= MAX_REQUEST_BYTES:
        chunk = connection.recv(min(4096, MAX_REQUEST_BYTES + 1 - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
        newline = payload.find(b"\n")
        if newline >= 0:
            return bytes(payload[:newline])
    return bytes(payload)


def request_read(
    capability: str,
    parameters: dict[str, Any] | None = None,
    *,
    socket_path: Path | str | None = None,
    request_id: str = "diagnostic",
) -> dict[str, Any]:
    """Issue one bounded diagnostic request to a running local broker."""
    frame = {
        "transport_version": TRANSPORT_VERSION,
        "request_id": request_id,
        "contract_version": PUBLIC_READ_CONTRACT_VERSION,
        "capability": capability,
        "parameters": parameters or {},
    }
    encoded = json.dumps(frame, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds transport limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SOCKET_TIMEOUT_SECONDS)
        client.connect(str(Path(socket_path) if socket_path else default_socket_path()))
        client.sendall(encoded)
        response = _read_response_line(client)
    return json.loads(response.decode("utf-8"))


def _read_response_line(connection: socket.socket) -> bytes:
    payload = bytearray()
    while len(payload) <= MAX_RESPONSE_BYTES:
        chunk = connection.recv(min(65536, MAX_RESPONSE_BYTES + 1 - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
        newline = payload.find(b"\n")
        if newline >= 0:
            return bytes(payload[:newline])
    raise TransportUnavailableError("broker response was missing or oversized")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="run the foreground read broker")
    serve.add_argument("--socket", type=Path, default=default_socket_path())
    read = subparsers.add_parser("read", help="issue one diagnostic read")
    read.add_argument("capability", choices=CANDIDATE_READS)
    read.add_argument("--parameters", default="{}", help="JSON object")
    read.add_argument("--socket", type=Path, default=default_socket_path())
    args = parser.parse_args(argv)
    if args.command == "serve":
        LocalReadBroker(args.socket).serve_forever()
        return 0
    try:
        parameters = json.loads(args.parameters)
    except json.JSONDecodeError as exc:
        parser.error(f"--parameters must be JSON: {exc.msg}")
    if not isinstance(parameters, dict):
        parser.error("--parameters must be a JSON object")
    print(json.dumps(request_read(args.capability, parameters, socket_path=args.socket), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
