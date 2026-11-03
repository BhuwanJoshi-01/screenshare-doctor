"""Secrets planted in the collected facts must not survive into any output (04 §6).

Each canary sits where the tool really reads data: the shell's and the user manager's
environment, a portal file and a probe failure. The tool must neither keep it (the
allowlists) nor print it (the redactor) in any renderer.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from rich.console import Console

from screenshare_doctor.models import FailureKind, ProbeFailure, Snapshot
from screenshare_doctor.orchestrator import diagnose, inspect_all
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.reports.findings import render_findings
from screenshare_doctor.reports.json_report import render_json
from screenshare_doctor.reports.markdown import render_markdown
from screenshare_doctor.reports.terminal import (
    render_dbus,
    render_desktop,
    render_route,
    render_services,
    render_session,
)
from tests.fakes import FakeRunner, read_env_fixture, read_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine, stat_socket_or_dir

CANARIES = ("ghp_CanaryToken0123456789abcdefABCDEF", "hunter2-canary-password", "alice")
ENV_SECRETS = {
    "GITHUB_TOKEN": CANARIES[0],
    "DB_PASSWORD": CANARIES[1],
    "HOME": "/home/alice",
}


def _snapshot() -> Snapshot:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    manager_env = read_fixture("systemctl", "show-environment-ubuntu-gnome.txt")
    manager_env += f"GITHUB_TOKEN={CANARIES[0]}\nDB_PASSWORD={CANARIES[1]}\n"
    runner.script("systemctl", "--user", "--no-pager", "show-environment", stdout=manager_env)
    read, list_dir = gnome_file_access(
        {
            "/home/user/.config/xdg-desktop-portal/portals.conf": (
                f"[preferred]\ndefault=gnome\n# token={CANARIES[0]}\n".encode()
            )
        }
    )
    snapshot = inspect_all(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu") | ENV_SECRETS,
        uid=1000,
        stat=stat_socket_or_dir,
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
        read=read,
        list_dir=list_dir,
    )
    failure = ProbeFailure("pw-dump", FailureKind.NONZERO_EXIT, f"failed: password={CANARIES[1]}")
    snapshot = dataclasses.replace(snapshot, probe_failures=(*snapshot.probe_failures, failure))
    context = RedactionContext(home="/home/alice", user="alice", hostname="alice-laptop")
    return redact_snapshot(diagnose(snapshot), context)


def _terminal(render: object, *args: object) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as capture:
        render(*args, console)  # type: ignore[operator]
    return capture.get()


@pytest.fixture(scope="module")
def outputs() -> dict[str, str]:
    snapshot = _snapshot()
    return {
        "json": render_json(snapshot),
        "markdown": render_markdown(snapshot),
        "doctor": _terminal(render_findings, snapshot),
        "session": _terminal(render_session, snapshot),
        "services": _terminal(render_services, snapshot),
        "dbus": _terminal(render_dbus, snapshot),
        "route": _terminal(render_route, snapshot, "org.freedesktop.impl.portal.ScreenCast"),
        "desktop": _terminal(render_desktop, snapshot, None, (), "test"),
    }


@pytest.mark.parametrize(
    "renderer", ["json", "markdown", "doctor", "session", "services", "dbus", "route", "desktop"]
)
@pytest.mark.parametrize("canary", CANARIES)
def test_no_canary_reaches_any_output(outputs: dict[str, str], renderer: str, canary: str) -> None:
    assert canary not in outputs[renderer]


def test_the_user_config_was_really_read(outputs: dict[str, str]) -> None:
    # The canary portals.conf (in the user manager's home) was found and its path redacted,
    # so the test is not vacuous.
    assert "/home/<user>/.config/xdg-desktop-portal: portals.conf" in outputs["route"]


def test_the_probe_failure_was_reported_redacted(outputs: dict[str, str]) -> None:
    assert "pw-dump: failed: password=" in outputs["doctor"]
    document = json.loads(outputs["json"])
    assert any(r["kind"] == "secret_value" for r in document["redactions"])
