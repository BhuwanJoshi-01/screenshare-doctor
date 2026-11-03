"""`screenshare-doctor check services`."""

from __future__ import annotations

import functools
import os
import stat
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.collectors.packages import DPKG_FORMAT, PACKAGES
from screenshare_doctor.collectors.services import UNIT_PROPERTIES, UNITS
from screenshare_doctor.privacy import RedactionContext, strip_control
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_env_fixture, read_fixture

SHOW = ["systemctl", "--user", "--no-pager", "show"]
SHOW += [part for name in UNIT_PROPERTIES for part in ("-p", name)]
SHOW += UNITS
SHOW_ENV = ("systemctl", "--user", "--no-pager", "show-environment")
SHOW_USER = ("loginctl", "--no-pager", "show-user", str(os.getuid()), "-p", "Display")


def _fake_stat(path: str) -> os.stat_result:
    mode = stat.S_IFDIR if path.endswith("/1000") else stat.S_IFSOCK
    return os.stat_result((mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))


def _run(monkeypatch: pytest.MonkeyPatch, runner: FakeRunner) -> int:
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli,
        "inspect_services",
        functools.partial(
            orchestrator.inspect_services,
            environ=read_env_fixture("gnome-wayland-ubuntu"),
            stat=_fake_stat,
            which=lambda name: f"/usr/bin/{name}" if name == "dpkg-query" else None,
            exists=lambda path: path == "/var/lib/dpkg/status",
        ),
    )
    monkeypatch.setattr(
        RedactionContext, "current", classmethod(lambda cls: RedactionContext(user="alice"))
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "services"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


def test_check_services_on_the_real_ubuntu_captures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout="Display=\n")
    runner.script(
        "dpkg-query",
        "-W",
        "-f",
        DPKG_FORMAT,
        *PACKAGES,
        stdout=read_fixture("packages", "dpkg-ubuntu-gnome.stdout"),
        stderr=read_fixture("packages", "dpkg-ubuntu-gnome.stderr"),
        returncode=1,
    )
    runner.script(*SHOW, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script(*SHOW_ENV, stdout=read_fixture("systemctl", "show-environment-ubuntu-gnome.txt"))
    assert _run(monkeypatch, runner) == 0
    out = strip_control(capsys.readouterr().out)
    assert "portal frontend" in out
    assert "1.21.1+ds-1ubuntu3.1" in out
    assert "(same as this shell)" in out


def test_without_systemd_it_still_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW_USER, Outcome.NOT_FOUND, error="No such file"))
    runner.script("dpkg-query", "-W", "-f", DPKG_FORMAT, *PACKAGES, stdout="pipewire\t1.6.2\tii \n")
    runner.script_result(CommandResult(tuple(SHOW), Outcome.NOT_FOUND, error="No such file"))
    assert _run(monkeypatch, runner) == 0
    out = strip_control(capsys.readouterr().out)
    assert "systemctl --user show: systemctl was not found" in out
    assert "not read (see below)" in out
