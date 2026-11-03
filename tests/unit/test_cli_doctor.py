"""`screenshare-doctor doctor` and `rules list|explain`."""

from __future__ import annotations

import functools
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext, strip_control
from screenshare_doctor.rules.catalog import builtin_rules
from tests.fakes import FIXTURES, FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine, stat_socket_or_dir


def _run(
    monkeypatch: pytest.MonkeyPatch, *args: str, extra_files: dict[str, bytes] | None = None
) -> int:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access(extra_files)
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli,
        "inspect_all",
        functools.partial(
            orchestrator.inspect_all,
            environ=read_env_fixture("gnome-wayland-ubuntu"),
            uid=1000,
            stat=stat_socket_or_dir,
            which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
            exists=lambda path: path == "/var/lib/dpkg/status",
            read=read,
            list_dir=list_dir,
        ),
    )
    monkeypatch.setattr(
        RedactionContext, "current", classmethod(lambda cls: RedactionContext(home="/home/user"))
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


DISABLED = {
    "/home/user/.config/xdg-desktop-portal/gnome-portals.conf": (
        b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"
    )
}


def test_doctor_on_the_real_machine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "doctor") == 0
    out = strip_control(capsys.readouterr().out)
    assert "Summary: 15 pass, 0 warn, 0 fail, 0 unknown" in out
    assert "secret" not in out


def test_strict_exits_1_only_on_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "doctor", "--strict") == 0
    assert _run(monkeypatch, "doctor", "--strict", extra_files=DISABLED) == 1
    out = strip_control(capsys.readouterr().out)
    assert "FAIL    SSD-PORTAL-002     ScreenCast is disabled by a portals.conf" in out


def test_without_strict_failures_still_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch, "doctor", extra_files=DISABLED) == 0


def test_rules_list_names_every_rule(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "rules", "list"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code in (0, None)
    out = strip_control(capsys.readouterr().out)
    for rule in builtin_rules():
        assert rule.id in out
    assert "SSD-PORTAL-002      portal-backend  ScreenCast has a backend that can answer" in out


def test_rules_explain(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "rules", "explain", "ssd-pw-001"])
    with pytest.raises(SystemExit):
        cli.main()
    out = strip_control(capsys.readouterr().out)
    assert "SSD-PW-001  PipeWire can carry the screen cast" in out
    assert "pipewire.socket" in out


def test_rules_explain_unknown_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "rules", "explain", "SSD-NOPE-001"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    assert "no check" in capsys.readouterr().err


def test_every_rule_is_documented() -> None:
    docs = (FIXTURES.parent.parent / "docs" / "rules.md").read_text(encoding="utf-8")
    for rule in builtin_rules():
        assert f"`{rule.id}`" in docs, rule.id
