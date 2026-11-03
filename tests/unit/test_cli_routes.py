"""`screenshare-doctor routes explain`."""

from __future__ import annotations

import functools
import os
import stat
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext, strip_control
from screenshare_doctor.routes import normalize_interface
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli,
        "inspect_routes",
        functools.partial(
            orchestrator.inspect_routes,
            environ=read_env_fixture("gnome-wayland-ubuntu"),
            uid=1000,
            stat=lambda path: os.stat_result((stat.S_IFSOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
            which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
            exists=lambda path: path == "/var/lib/dpkg/status",
            read=read,
            list_dir=list_dir,
        ),
    )
    monkeypatch.setattr(
        RedactionContext,
        "current",
        classmethod(lambda cls: RedactionContext(home="/home/user", user="user")),
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "routes", "explain", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


def test_default_interface_is_screencast(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch) == 0
    out = " ".join(strip_control(capsys.readouterr().out).split())
    assert "route for ScreenCast" in out
    assert "Predicted gnome" in out
    assert "~/.config/xdg-desktop-portal: nothing" in out
    assert "/home/user" not in out


@pytest.mark.parametrize(
    "name",
    ["Screenshot", "org.freedesktop.portal.Screenshot", "org.freedesktop.impl.portal.Screenshot"],
)
def test_interface_names_in_every_form(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    assert _run(monkeypatch, name) == 0
    assert "route for Screenshot" in strip_control(capsys.readouterr().out)


def test_invalid_interface_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "Screen Cast") == 2
    assert "is not a portal interface name" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("name", "impl"),
    [
        ("ScreenCast", "org.freedesktop.impl.portal.ScreenCast"),
        ("org.freedesktop.portal.ScreenCast", "org.freedesktop.impl.portal.ScreenCast"),
        ("org.freedesktop.impl.portal.ScreenCast", "org.freedesktop.impl.portal.ScreenCast"),
        ("org.freedesktop.portal.", None),
        ("../x", None),
        ("", None),
        ("com.example.ScreenCast", None),
    ],
)
def test_normalize_interface(name: str, impl: str | None) -> None:
    assert normalize_interface(name) == impl
