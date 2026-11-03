"""Checking the runtime directory and display sockets (WLD-001)."""

from __future__ import annotations

import os
import socket
import stat
from pathlib import Path

import pytest

from screenshare_doctor.collectors.environment import X11_SOCKET_DIR, check_session_paths
from screenshare_doctor.models import PathState, SessionEnvironment

pytestmark = pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="needs UNIX sockets")


@pytest.fixture
def runtime_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # A short path: UNIX socket names are limited to about 100 bytes.
    return tmp_path_factory.mktemp("rt")


def _listen(path: Path) -> socket.socket:
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    return server


def test_existing_wayland_socket_is_found(runtime_dir: Path) -> None:
    with _listen(runtime_dir / "wayland-0"):
        paths = check_session_paths(
            SessionEnvironment(wayland_display="wayland-0", runtime_dir=str(runtime_dir))
        )
    assert paths.runtime_dir is PathState.DIRECTORY
    assert paths.wayland_socket is PathState.SOCKET
    assert paths.wayland_socket_path == f"{runtime_dir}/wayland-0"


def test_missing_wayland_socket(runtime_dir: Path) -> None:
    paths = check_session_paths(
        SessionEnvironment(wayland_display="wayland-1", runtime_dir=str(runtime_dir))
    )
    assert paths.wayland_socket is PathState.MISSING


def test_regular_file_is_not_a_socket(runtime_dir: Path) -> None:
    (runtime_dir / "wayland-0").write_text("")
    paths = check_session_paths(
        SessionEnvironment(wayland_display="wayland-0", runtime_dir=str(runtime_dir))
    )
    assert paths.wayland_socket is PathState.OTHER


def test_absolute_wayland_display_is_used_as_is(runtime_dir: Path) -> None:
    with _listen(runtime_dir / "custom"):
        paths = check_session_paths(SessionEnvironment(wayland_display=str(runtime_dir / "custom")))
    assert paths.wayland_socket is PathState.SOCKET
    assert paths.runtime_dir is PathState.NOT_CHECKED


def test_relative_wayland_display_without_runtime_dir_is_not_guessed() -> None:
    paths = check_session_paths(SessionEnvironment(wayland_display="wayland-0"))
    assert paths.wayland_socket is PathState.NOT_CHECKED
    assert paths.wayland_socket_path is None


def test_missing_runtime_dir(tmp_path: Path) -> None:
    paths = check_session_paths(SessionEnvironment(runtime_dir=str(tmp_path / "gone")))
    assert paths.runtime_dir is PathState.MISSING


def test_runtime_dir_that_is_a_file(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("")
    paths = check_session_paths(SessionEnvironment(runtime_dir=str(tmp_path / "file")))
    assert paths.runtime_dir is PathState.OTHER


def test_nothing_set_checks_nothing() -> None:
    def no_stat(path: str) -> os.stat_result:
        raise AssertionError(f"stat({path!r}) without a variable pointing there")

    paths = check_session_paths(SessionEnvironment(), stat=no_stat)
    assert paths.runtime_dir is PathState.NOT_CHECKED
    assert paths.wayland_socket is PathState.NOT_CHECKED
    assert paths.x11_socket is PathState.NOT_CHECKED


@pytest.mark.parametrize(
    ("display", "socket_path"),
    [
        (":0", f"{X11_SOCKET_DIR}/X0"),
        (":1.0", f"{X11_SOCKET_DIR}/X1"),
        ("unix:12", f"{X11_SOCKET_DIR}/X12"),
        ("localhost:10.0", None),
        ("garbage", None),
    ],
)
def test_x11_socket_path(display: str, socket_path: str | None) -> None:
    def fake_stat(path: str) -> os.stat_result:
        return os.stat_result((stat.S_IFSOCK | 0o777, 0, 0, 0, 0, 0, 0, 0, 0, 0))

    paths = check_session_paths(SessionEnvironment(display=display), stat=fake_stat)
    assert paths.x11_socket_path == socket_path
    assert paths.x11_socket is (PathState.SOCKET if socket_path else PathState.NOT_CHECKED)


def test_unreadable_path_is_not_missing() -> None:
    def denied(path: str) -> os.stat_result:
        raise PermissionError(13, "Permission denied", path)

    paths = check_session_paths(
        SessionEnvironment(runtime_dir="/run/user/1000", wayland_display="wayland-0"), stat=denied
    )
    assert paths.runtime_dir is PathState.UNREADABLE
    assert paths.wayland_socket is PathState.UNREADABLE


def test_trailing_slash_in_runtime_dir() -> None:
    paths = check_session_paths(
        SessionEnvironment(runtime_dir="/run/user/1000/", wayland_display="wayland-0"),
        stat=lambda path: os.stat_result((stat.S_IFSOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
    )
    assert paths.wayland_socket_path == "/run/user/1000/wayland-0"
