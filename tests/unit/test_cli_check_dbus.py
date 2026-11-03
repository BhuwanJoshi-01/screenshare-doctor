"""`screenshare-doctor check dbus`."""

from __future__ import annotations

import sys

import pytest

from screenshare_doctor import cli
from screenshare_doctor.privacy import strip_control
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner
from tests.scenarios import BUS_DAEMON, script_gnome_bus


def _run(monkeypatch: pytest.MonkeyPatch, runner: FakeRunner) -> int:
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "dbus"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


def test_real_gnome_bus_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    script_gnome_bus(runner)
    assert _run(monkeypatch, runner) == 0
    out = strip_control(capsys.readouterr().out)
    assert "Session bus reachable" in out
    assert "version 5; sources: monitor, window," in out  # wrapped at 80 columns


def test_unreachable_bus_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script(
        *BUS_DAEMON,
        "ListActivatableNames",
        stderr="Failed to connect to user scope bus via local transport: No such file or directory",
        returncode=1,
    )
    assert _run(monkeypatch, runner) == 3
    assert "not reachable" in strip_control(capsys.readouterr().out)


def test_missing_busctl_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner()
    runner.script_result(
        CommandResult(
            (*BUS_DAEMON, "ListActivatableNames"), Outcome.NOT_FOUND, error="No such file"
        )
    )
    assert _run(monkeypatch, runner) == 3
