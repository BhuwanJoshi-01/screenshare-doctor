"""`screenshare-doctor troubleshoot screenshare` (WLD-006)."""

from __future__ import annotations

import functools
import sys

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext, strip_control
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine, stat_socket_or_dir

DISABLED = {
    "/home/user/.config/xdg-desktop-portal/gnome-portals.conf": (
        b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"
    )
}


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *args: str,
    extra_files: dict[str, bytes] | None = None,
    flatpaks: frozenset[str] = frozenset(),
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
        cli,
        "installed_flatpaks",
        lambda ids, home: tuple(i for i in ids if i in flatpaks),
    )
    monkeypatch.setattr(
        RedactionContext, "current", classmethod(lambda cls: RedactionContext(home="/home/user"))
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", "troubleshoot", "screenshare", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    return code if isinstance(code, int) else 0


def _out(capsys: pytest.CaptureFixture[str]) -> str:
    return " ".join(strip_control(capsys.readouterr().out).split())


def test_firefox_without_a_picker_on_the_real_machine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "--app", "firefox", "--symptom", "no-picker") == 0
    out = _out(capsys)
    assert "Firefox: Clicking Share shows no screen or window picker" in out
    assert "Checked, most likely cause first:" in out
    assert "None of these checks found a problem" in out
    assert "Firefox 121 and later run natively on Wayland" in out
    assert "https://www.mozilla.org/firefox/121.0/releasenotes/" in out


def test_disabled_screencast_is_the_likely_cause(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        _run(monkeypatch, "--app", "discord", "--symptom", "no-picker", extra_files=DISABLED) == 0
    )
    out = _out(capsys)
    assert "Most likely: SSD-PORTAL-002: ScreenCast is disabled by a portals.conf" in out
    assert "Electron apps" in out


def test_flatpak_app_gets_the_portal_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    flatpaks = frozenset({"com.obsproject.Studio"})
    assert _run(monkeypatch, "--app", "obs", "--symptom", "black-screen", flatpaks=flatpaks) == 0
    out = _out(capsys)
    assert "Installed as a Flatpak: com.obsproject.Studio" in out
    assert "always share through the portal" in out
    assert "Source (low confidence)" in out


def test_unknown_app_still_gets_the_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "--app", "zoom", "--symptom", "missing-window") == 0
    out = _out(capsys)
    assert "No profile for 'zoom'; the checks above apply to any app." in out
    assert "SSD-PORTAL-004" in out


def test_permission_symptom_names_what_is_not_checked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "--symptom", "permission-denied") == 0
    assert "Not checked: The portal's permission store" in _out(capsys)


def test_explain_shows_why_each_check_passed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, "--symptom", "black-screen", "--explain") == 0
    out = _out(capsys)
    assert "pw-dump reached the daemon." in out  # a PASS reason
    assert "A Wayland screen cast is a PipeWire stream" in out  # the rule's explanation


def test_no_symptom_runs_every_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch) == 0
    out = _out(capsys)
    assert "any app: every check" in out
    assert out.count("PASS ") == 15


def test_unknown_symptom_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["screenshare-doctor", "troubleshoot", "screenshare", "--symptom", "slow"]
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown symptom 'slow'" in err
    assert "no-picker" in err
