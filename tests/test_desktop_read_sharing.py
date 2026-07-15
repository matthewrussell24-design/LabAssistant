from io import StringIO
import os
from pathlib import Path
import tempfile
import threading

import pytest

import labassistant.desktop as desktop
import labassistant.desktop_read_sharing as sharing
import labassistant.local_read_transport as transport
import labassistant.ui.macos_window as macos_window


@pytest.fixture
def short_socket_path():
    runtime = Path(tempfile.mkdtemp(prefix="la-desktop-", dir="/tmp"))
    runtime.chmod(0o700)
    try:
        yield runtime / "read.sock"
    finally:
        for child in runtime.iterdir():
            child.unlink()
        runtime.rmdir()


def broker_factory(path):
    owner = transport.PeerCredentials(uid=os.getuid(), gid=os.getgid())
    return transport.LocalReadBroker(path, credential_resolver=lambda _: owner)


def test_owner_serves_typed_reads_and_cleans_up_owned_socket(short_socket_path):
    owner = sharing.DesktopReadBrokerOwner(
        short_socket_path,
        broker_factory=broker_factory,
    )
    status = owner.start()
    assert status.state == sharing.OWNED
    assert short_socket_path.exists()

    result = sharing.LocalReadClient(short_socket_path).describe_platform()
    assert result.data.contract_version == "1.0"
    assert len(result.data.capabilities) == 7

    final_status = owner.close()
    assert final_status.state == sharing.DISABLED
    assert not short_socket_path.exists()
    assert owner.close() == final_status


def test_compatible_external_broker_is_recognized_and_never_closed(short_socket_path):
    existing = broker_factory(short_socket_path)
    existing.start()
    stop_event = threading.Event()
    worker = threading.Thread(target=existing.serve_until, args=(stop_event,), daemon=True)
    worker.start()
    try:
        owner = sharing.DesktopReadBrokerOwner(short_socket_path)
        status = owner.start()
        assert status.state == sharing.EXTERNAL
        assert owner.close().state == sharing.EXTERNAL
        assert short_socket_path.exists()
        assert sharing.LocalReadClient(short_socket_path).describe_platform().api_version == "1.0"
    finally:
        stop_event.set()
        existing.close()
        worker.join(timeout=1)
    assert not short_socket_path.exists()


def test_unsafe_or_incompatible_collision_does_not_replace_path(short_socket_path):
    short_socket_path.write_text("keep")
    owner = sharing.DesktopReadBrokerOwner(short_socket_path)
    assert owner.start().state == sharing.UNSAFE_PATH
    assert short_socket_path.read_text() == "keep"

    class CollisionBroker:
        def start(self):
            raise transport.BrokerAlreadyRunningError()

    class IncompatibleClient:
        def describe_platform(self):
            raise sharing.LocalReadClientError("incompatible")

    owner = sharing.DesktopReadBrokerOwner(
        short_socket_path,
        broker_factory=lambda path: CollisionBroker(),
        client_factory=lambda path: IncompatibleClient(),
    )
    assert owner.start().state == sharing.INCOMPATIBLE
    assert short_socket_path.read_text() == "keep"


def test_desktop_default_is_listener_free_and_preserves_initial_paths(monkeypatch):
    calls = []
    monkeypatch.setattr(
        macos_window,
        "run_native_workspace",
        lambda analyzer, paths: calls.append(tuple(paths)),
    )

    def forbidden_owner(*args):
        raise AssertionError("owner must not be created")

    assert desktop.run_desktop(
        ["one.xlsx"], owner_factory=forbidden_owner
    ) is None
    assert calls == [("one.xlsx",)]


def test_opt_in_reports_status_and_closes_owner_when_appkit_fails(monkeypatch):
    events = []
    status = sharing.DesktopReadSharingStatus(sharing.OWNED, Path("/safe/read.sock"))

    class FakeOwner:
        def start(self):
            events.append("start")
            return status

        def close(self):
            events.append("close")
            return sharing.DesktopReadSharingStatus(
                sharing.DISABLED, status.socket_path
            )

    monkeypatch.setattr(
        macos_window,
        "run_native_workspace",
        lambda analyzer, paths, termination_callback=None: (_ for _ in ()).throw(
            RuntimeError("app failed")
        ),
    )
    output = StringIO()
    with pytest.raises(RuntimeError, match="app failed"):
        desktop.run_desktop(
            ["one.xlsx"],
            share_local_reads=True,
            owner_factory=lambda path: FakeOwner(),
            status_stream=output,
        )
    assert events == ["start", "close"]
    assert "owned and available" in output.getvalue()
    assert "app failed" not in output.getvalue()


def test_desktop_argument_parser_separates_opt_in_from_paths():
    args = desktop.parse_desktop_args(
        ["--share-local-reads", "--read-socket", "/safe/read.sock", "one.xlsx"]
    )
    assert args.share_local_reads is True
    assert args.read_socket == Path("/safe/read.sock")
    assert args.paths == ["one.xlsx"]

    plain = desktop.parse_desktop_args(["one.xlsx", "two.xlsx"])
    assert plain.share_local_reads is False
    assert plain.paths == ["one.xlsx", "two.xlsx"]

    with pytest.raises(SystemExit):
        desktop.parse_desktop_args(["--read-socket", "/safe/read.sock"])


def test_status_messages_use_bounded_categories_without_exception_details():
    path = Path("/safe/read.sock")
    for state in (
        sharing.OWNED,
        sharing.EXTERNAL,
        sharing.UNSAFE_PATH,
        sharing.INCOMPATIBLE,
        sharing.UNAVAILABLE,
        sharing.DISABLED,
        sharing.SHUTDOWN_FAILED,
    ):
        message = sharing.DesktopReadSharingStatus(state, path).message()
        assert state not in {"Traceback", "Exception"}
        assert str(path) in message


def test_appkit_termination_delegate_runs_idempotent_owner_cleanup():
    calls = []
    delegate = macos_window.ApplicationDelegate.alloc().initWithTerminationCallback_(
        lambda: calls.append("close")
    )
    delegate.applicationWillTerminate_(None)
    assert calls == ["close"]
