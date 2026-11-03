"""`screenshare-doctor check session`."""

from __future__ import annotations

import functools
import os
import stat
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext, strip_control
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_env_fixture, read_fixture

PROPS = tuple(
    part
    for name in ("Id", "Type", "Class", "Remote", "Desktop", "State", "Active", "Seat")
    for part in ("-p", name)
)


def _show_user(uid: int) -> tuple[str, ...]:
    return ("loginctl", "--no-pager", "show-user", str(uid), "-p", "Display")


def _fake_stat(path: str) -> os.stat_result:
    mode = stat.S_IFDIR if path.endswith("/1000") else stat.S_IFSOCK
    return os.stat_result((mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))


def _run(monkeypatch: pytest.MonkeyPatch, runner: FakeRunner, environ: dict[str, str]) -> int:
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli,
        "inspect_session",
        functools.partial(orchestrator.inspect_session, environ=environ, stat=_fake_stat),
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "session"])
    monkeypatch.setattr(
        RedactionContext,
        "current",
        classmethod(lambda cls: RedactionContext(home="/home/alice", user="alice")),
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


def test_gnome_wayland_session_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script(*_show_user(os.getuid()), stdout="Display=63\n")
    runner.script(
        "loginctl",
        "--no-pager",
        "show-session",
        "63",
        *PROPS,
        stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt"),
    )
    assert _run(monkeypatch, runner, read_env_fixture("gnome-wayland-ubuntu")) == 0
    out = strip_control(capsys.readouterr().out)
    assert "Wayland (from this environment)" in out
    assert "GNOME (XDG_CURRENT_DESKTOP=ubuntu:GNOME)" in out


def test_no_session_and_no_logind_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    argv = _show_user(os.getuid())
    runner.script_result(CommandResult(argv, Outcome.NOT_FOUND, error="No such file"))
    assert _run(monkeypatch, runner, {}) == 3
    out = strip_control(capsys.readouterr().out)
    assert "loginctl was not found" in out


def test_text_console_without_graphical_session_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script(
        "loginctl",
        "--no-pager",
        "show-session",
        "5",
        *PROPS,
        stdout="Id=5\nSeat=seat0\nRemote=no\nType=tty\nClass=user\nActive=yes\nState=active\n",
    )
    runner.script(*_show_user(os.getuid()), stdout="Display=\n")
    assert _run(monkeypatch, runner, read_env_fixture("linux-console")) == 3
    out = strip_control(capsys.readouterr().out)
    assert "a text console" in out
    assert "no graphical session for this user; this login: session 5: tty" in out


def test_output_is_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script(*_show_user(os.getuid()), stdout="Display=\n")
    environ = {"WAYLAND_DISPLAY": "/home/alice/.wl/wayland-0", "XDG_SESSION_TYPE": "wayland"}
    assert _run(monkeypatch, runner, environ) == 0
    out = strip_control(capsys.readouterr().out)
    assert "~/.wl/wayland-0" in out
    assert "alice" not in out
    assert "Redacted from this output: 2 home paths" in out  # variable + socket path


def test_help_lists_check_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "--help"])
    with pytest.raises(SystemExit):
        cli.main()
    assert "session" in strip_control(capsys.readouterr().out)
