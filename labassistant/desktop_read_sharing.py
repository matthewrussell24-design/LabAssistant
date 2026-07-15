"""Explicit process-bounded ownership for desktop local-read sharing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable

from labassistant.api_readiness import CANDIDATE_READS, PUBLIC_READ_CONTRACT_VERSION
from labassistant.local_read_client import LocalReadClient, LocalReadClientError
from labassistant.local_read_transport import (
    BrokerAlreadyRunningError,
    LocalReadBroker,
    UnsafeSocketPathError,
    default_socket_path,
)


OWNED = "owned"
EXTERNAL = "external"
UNSAFE_PATH = "unsafe_path"
INCOMPATIBLE = "incompatible"
UNAVAILABLE = "unavailable"
DISABLED = "disabled"
SHUTDOWN_FAILED = "shutdown_failed"


@dataclass(frozen=True)
class DesktopReadSharingStatus:
    state: str
    socket_path: Path

    def message(self) -> str:
        descriptions = {
            OWNED: "owned and available",
            EXTERNAL: "compatible external broker available",
            UNSAFE_PATH: "unavailable (unsafe socket path)",
            INCOMPATIBLE: "unavailable (incompatible existing broker)",
            UNAVAILABLE: "unavailable",
            DISABLED: "disabled",
            SHUTDOWN_FAILED: "shutdown did not complete cleanly",
        }
        return f"LabAssistant local reads: {descriptions[self.state]} [{self.socket_path}]"


class DesktopReadBrokerOwner:
    """Own or recognize one broker without importing or touching AppKit."""

    def __init__(
        self,
        socket_path: Path | str | None = None,
        *,
        broker_factory: Callable[[Path], LocalReadBroker] = LocalReadBroker,
        client_factory: Callable[[Path], LocalReadClient] = LocalReadClient,
        join_timeout: float = 1.0,
    ) -> None:
        self.socket_path = Path(socket_path) if socket_path else default_socket_path()
        self._broker_factory = broker_factory
        self._client_factory = client_factory
        self._join_timeout = join_timeout
        self._broker: LocalReadBroker | None = None
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self.status = DesktopReadSharingStatus(DISABLED, self.socket_path)

    def start(self) -> DesktopReadSharingStatus:
        if self.status.state != DISABLED:
            return self.status
        broker = self._broker_factory(self.socket_path)
        try:
            broker.start()
        except BrokerAlreadyRunningError:
            self.status = self._probe_external()
            return self.status
        except UnsafeSocketPathError:
            self.status = DesktopReadSharingStatus(UNSAFE_PATH, self.socket_path)
            return self.status
        except Exception:
            self.status = DesktopReadSharingStatus(UNAVAILABLE, self.socket_path)
            return self.status

        stop_event = threading.Event()
        worker = threading.Thread(
            target=self._serve,
            args=(broker, stop_event),
            name="labassistant-local-read-broker",
            daemon=True,
        )
        self._broker = broker
        self._stop_event = stop_event
        self._worker = worker
        worker.start()
        self.status = DesktopReadSharingStatus(OWNED, self.socket_path)
        return self.status

    def close(self) -> DesktopReadSharingStatus:
        if self.status.state != OWNED:
            return self.status
        broker = self._broker
        worker = self._worker
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        if broker is not None:
            broker.close()
        if worker is not None:
            worker.join(self._join_timeout)
        if worker is not None and worker.is_alive():
            self.status = DesktopReadSharingStatus(SHUTDOWN_FAILED, self.socket_path)
        else:
            self.status = DesktopReadSharingStatus(DISABLED, self.socket_path)
        self._broker = None
        self._stop_event = None
        self._worker = None
        return self.status

    def _serve(self, broker: LocalReadBroker, stop_event: threading.Event) -> None:
        try:
            broker.serve_until(stop_event)
        except Exception:
            # Operational status is reported by the owner; worker internals are
            # never printed or exposed through the stable application contract.
            return

    def _probe_external(self) -> DesktopReadSharingStatus:
        try:
            result = self._client_factory(self.socket_path).describe_platform()
        except LocalReadClientError:
            return DesktopReadSharingStatus(INCOMPATIBLE, self.socket_path)
        except Exception:
            return DesktopReadSharingStatus(UNAVAILABLE, self.socket_path)
        capability_names = tuple(item.name for item in result.data.capabilities)
        if (
            result.api_version == PUBLIC_READ_CONTRACT_VERSION
            and result.data.contract_version == PUBLIC_READ_CONTRACT_VERSION
            and capability_names == CANDIDATE_READS
        ):
            return DesktopReadSharingStatus(EXTERNAL, self.socket_path)
        return DesktopReadSharingStatus(INCOMPATIBLE, self.socket_path)
