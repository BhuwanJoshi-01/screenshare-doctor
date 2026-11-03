from __future__ import annotations

import os
import stat

from screenshare_doctor import __version__
from screenshare_doctor.models import FailureKind, PathState, SessionEnvironment
from screenshare_doctor.orchestrator import collect_session, inspect_session
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_env_fixture, read_fixture

SHOW_USER = ("loginctl", "--no-pager", "show-user", "1000", "-p", "Display")
SHOW_63 = ("loginctl", "--no-pager", "show-session", "63")
SHOW_63 += tuple(
    part
    for name in ("Id", "Type", "Class", "Remote", "Desktop", "State", "Active", "Seat")
    for part in ("-p", name)
)


def _socket_stat(path: str) -> os.stat_result:
    mode = stat.S_IFDIR if path == "/run/user/1000" else stat.S_IFSOCK
    return os.stat_result((mode | 0o700, 0, 0, 0, 0, 0, 0, 0, 0, 0))


def _gnome_runner() -> FakeRunner:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout=read_fixture("loginctl", "show-user-display-gnome.txt"))
    runner.script(*SHOW_63, stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt"))
    return runner


def test_collect_session_on_the_real_gnome_capture() -> None:
    facts, failures = collect_session(
        _gnome_runner(),
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
    )
    assert failures == ()
    assert facts.environment.current_desktop == "ubuntu:GNOME"
    assert facts.paths.wayland_socket is PathState.SOCKET
    assert facts.logind.display is not None
    assert facts.logind.display.id == "63"


def test_inspect_session_builds_a_snapshot() -> None:
    snapshot = inspect_session(
        _gnome_runner(),
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
    )
    assert snapshot.tool_version == __version__
    assert snapshot.session is not None
    assert snapshot.probe_failures == ()


def test_missing_loginctl_is_a_probe_failure_in_the_snapshot() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW_USER, Outcome.NOT_FOUND, error="No such file"))
    snapshot = inspect_session(runner, environ={}, uid=1000, stat=_socket_stat)
    assert snapshot.session is not None
    assert snapshot.session.environment == SessionEnvironment()
    assert [f.kind for f in snapshot.probe_failures] == [FailureKind.NOT_FOUND]


def test_session_facts_survive_redaction() -> None:
    snapshot = inspect_session(
        _gnome_runner(),
        environ=read_env_fixture("gnome-wayland-ubuntu")
        | {"XDG_RUNTIME_DIR": "/home/alice/.run", "WAYLAND_DISPLAY": "/home/alice/.run/wl"},
        uid=1000,
        stat=_socket_stat,
    )
    context = RedactionContext(home="/home/alice", user="alice", hostname="alice-laptop")
    redacted = redact_snapshot(snapshot, context)
    assert redacted.session is not None
    assert redacted.session.environment.runtime_dir == "~/.run"
    assert redacted.session.paths.wayland_socket_path == "~/.run/wl"
    assert "alice" not in repr(redacted)
