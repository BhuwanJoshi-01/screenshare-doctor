"""`screenshare-doctor check desktop` (WLD-007)."""

from __future__ import annotations

import functools
import os
import stat
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext, strip_control
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine


def _run(
    monkeypatch: pytest.MonkeyPatch, *args: str, environ: dict[str, str] | None = None
) -> None:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli,
        "inspect_routes",
        functools.partial(
            orchestrator.inspect_routes,
            environ=environ or read_env_fixture("gnome-wayland-ubuntu"),
            uid=1000,
            stat=lambda path: os.stat_result((stat.S_IFSOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
            which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
            exists=lambda path: path == "/var/lib/dpkg/status",
            read=read,
            list_dir=list_dir,
        ),
    )
    monkeypatch.setattr(
        RedactionContext, "current", classmethod(lambda cls: RedactionContext(home="/home/user"))
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "desktop", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code in (0, None)


def test_detected_gnome_passes_everything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(monkeypatch)
    out = strip_control(capsys.readouterr().out)
    assert "Desktop     GNOME (from XDG_CURRENT_DESKTOP of the user manager)" in out
    assert out.count("PASS    ") == 6
    assert "FAIL" not in out


def test_compared_as_kde(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(monkeypatch, "--as", "kde")
    out = strip_control(capsys.readouterr().out)
    assert "Desktop     KDE Plasma (chosen with --as)" in out
    assert "FAIL    xdg-desktop-portal-kde is installed" in out
    assert "WARN    kde-portals.conf is installed" in out
    assert "plasma-workspace installs it" in out
    assert "N/A     the compositor offers screen casts" in out


def test_invalid_choice_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "check", "desktop", "--as", "windows"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
