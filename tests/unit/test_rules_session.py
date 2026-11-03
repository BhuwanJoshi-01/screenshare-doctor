"""Session rules (SSD-SESSION-*)."""

from __future__ import annotations

import dataclasses
import os
import stat

import pytest

from screenshare_doctor.models import (
    Finding,
    LogindFacts,
    LogindSession,
    PathState,
    ServiceFacts,
    SessionEnvironment,
    SessionFacts,
    SessionPaths,
    Snapshot,
    Status,
)
from screenshare_doctor.orchestrator import inspect_services
from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.rules.engine import evaluate
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import script_gnome_machine

WAYLAND = SessionEnvironment(
    session_type="wayland",
    current_desktop="Hyprland",
    wayland_display="wayland-1",
    runtime_dir="/run/user/1000",
)
SOCKET = SessionPaths(
    runtime_dir=PathState.DIRECTORY,
    wayland_socket=PathState.SOCKET,
    wayland_socket_path="/run/user/1000/wayland-1",
)


@pytest.fixture(scope="module")
def real() -> Snapshot:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    return inspect_services(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=lambda path: os.stat_result(
            ((stat.S_IFDIR if path.endswith("/1000") else stat.S_IFSOCK), 0, 0, 0, 0, 0, 0, 0, 0, 0)
        ),
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
    )


def _findings(snapshot: Snapshot) -> dict[str, Finding]:
    rules = [rule for rule in builtin_rules() if rule.id.startswith("SSD-SESSION-")]
    return {finding.id: finding for finding in evaluate(snapshot, rules)}


def _snapshot(
    env: SessionEnvironment = WAYLAND,
    paths: SessionPaths = SOCKET,
    logind: LogindFacts | None = None,
    activation: SessionEnvironment | None = WAYLAND,
) -> Snapshot:
    return Snapshot(
        tool_version="0.1.0",
        created_at="x",
        session=SessionFacts(env, paths, logind or LogindFacts()),
        services=ServiceFacts(services=(), activation_environment=activation),
    )


def test_real_gnome_machine_passes_every_session_rule(real: Snapshot) -> None:
    findings = _findings(real)
    assert {key: f.status for key, f in findings.items()} == {
        "SSD-SESSION-001": Status.PASS,
        "SSD-SESSION-002": Status.PASS,
        "SSD-SESSION-003": Status.PASS,
        "SSD-SESSION-004": Status.PASS,
    }
    assert findings["SSD-SESSION-003"].summary == "The portal reads the desktop names ubuntu, gnome"


def test_x11_session_warns() -> None:
    env = SessionEnvironment(session_type="x11", display=":0", current_desktop="GNOME")
    findings = _findings(_snapshot(env, SessionPaths(), activation=env))
    assert findings["SSD-SESSION-001"].status is Status.WARN
    assert "SSD-SESSION-002" not in findings  # only judged on Wayland


def test_no_graphical_session_fails() -> None:
    env = SessionEnvironment(session_type="tty")
    findings = _findings(
        _snapshot(env, SessionPaths(), LogindFacts(display_known=True), activation=env)
    )
    assert findings["SSD-SESSION-001"].status is Status.FAIL


def test_unknown_session_is_unknown_not_pass() -> None:
    findings = _findings(_snapshot(SessionEnvironment(), SessionPaths(), activation=None))
    assert findings["SSD-SESSION-001"].status is Status.UNKNOWN


def test_stale_wayland_socket_fails() -> None:
    paths = dataclasses.replace(SOCKET, wayland_socket=PathState.MISSING)
    finding = _findings(_snapshot(paths=paths))["SSD-SESSION-002"]
    assert finding.status is Status.FAIL
    assert "left over" in finding.reason


def test_xwayland_only_shell_warns() -> None:
    env = dataclasses.replace(WAYLAND, wayland_display=None, display=":0")
    finding = _findings(_snapshot(env, SessionPaths(), activation=env))["SSD-SESSION-002"]
    assert finding.status is Status.WARN
    assert "XWayland" in finding.reason


def test_ssh_login_does_not_judge_its_own_display() -> None:
    env = SessionEnvironment(session_type="tty", ssh=True)
    logind = LogindFacts(display=LogindSession(id="2", session_type="wayland"), display_known=True)
    findings = _findings(_snapshot(env, SessionPaths(), logind, activation=WAYLAND))
    assert findings["SSD-SESSION-001"].status is Status.PASS
    assert findings["SSD-SESSION-002"].status is Status.NOT_APPLICABLE
    assert "SSD-SESSION-004" not in findings


def test_portal_without_desktop_name() -> None:
    activation = dataclasses.replace(WAYLAND, current_desktop=None)
    finding = _findings(_snapshot(activation=activation))["SSD-SESSION-003"]
    assert finding.status is Status.WARN
    assert "the user manager" in finding.reason


def test_portal_ignores_part_of_the_desktop_name() -> None:
    activation = dataclasses.replace(WAYLAND, current_desktop="ubuntu: GNOME")
    finding = _findings(_snapshot(activation=activation))["SSD-SESSION-003"]
    assert finding.status is Status.WARN
    assert "' GNOME'" in finding.reason


def test_hyprland_without_exported_variables() -> None:
    finding = _findings(_snapshot(activation=SessionEnvironment()))["SSD-SESSION-004"]
    assert finding.status is Status.FAIL
    assert finding.recommended_action is not None
    assert "dbus-update-activation-environment" in finding.recommended_action
    assert finding.verify_command is not None


def test_different_desktop_name_in_the_user_manager() -> None:
    activation = dataclasses.replace(WAYLAND, current_desktop="GNOME")
    finding = _findings(_snapshot(activation=activation))["SSD-SESSION-004"]
    assert finding.status is Status.WARN


def test_unreadable_user_manager_is_unknown() -> None:
    assert _findings(_snapshot(activation=None))["SSD-SESSION-004"].status is Status.UNKNOWN


def test_rules_stay_silent_without_their_facts() -> None:
    assert _findings(Snapshot(tool_version="0.1.0", created_at="x")) == {}
