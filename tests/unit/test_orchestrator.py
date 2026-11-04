from __future__ import annotations

import os
import stat

from screenshare_doctor import __version__
from screenshare_doctor.collectors.packages import DPKG_FORMAT, PACKAGES
from screenshare_doctor.collectors.services import UNIT_PROPERTIES, UNITS
from screenshare_doctor.models import FailureKind, PathState, SessionEnvironment, Status
from screenshare_doctor.orchestrator import (
    collect_session,
    diagnose,
    inspect_all,
    inspect_dbus,
    inspect_routes,
    inspect_services,
    inspect_session,
)
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_env_fixture, read_fixture
from tests.scenarios import (
    gnome_file_access,
    script_gnome_bus,
    script_gnome_machine,
    script_gnome_pipewire,
)

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


def test_inspect_services_collects_session_packages_and_services() -> None:
    runner = _gnome_runner()
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
    show = ["systemctl", "--user", "--no-pager", "show"]
    show += [part for name in UNIT_PROPERTIES for part in ("-p", name)]
    runner.script(*show, *UNITS, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script(
        "systemctl",
        "--user",
        "--no-pager",
        "show-environment",
        stdout=read_fixture("systemctl", "show-environment-ubuntu-gnome.txt"),
    )
    script_gnome_pipewire(runner)
    snapshot = inspect_services(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
    )
    assert snapshot.probe_failures == ()
    assert snapshot.session is not None
    assert snapshot.packages is not None
    assert snapshot.packages.source == "dpkg"
    assert snapshot.services is not None
    assert snapshot.services.activation_environment is not None
    assert snapshot.pipewire is not None
    assert snapshot.pipewire.version == "1.6.2"


def test_inspect_dbus_on_the_real_gnome_bus() -> None:
    runner = FakeRunner()
    script_gnome_bus(runner)
    snapshot = inspect_dbus(runner)
    assert snapshot.probe_failures == ()
    assert snapshot.dbus is not None
    assert snapshot.dbus.reachable is True
    assert snapshot.session is None


def test_inspect_routes_on_the_real_machine() -> None:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    snapshot = inspect_routes(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
        read=read,
        list_dir=list_dir,
    )
    assert snapshot.probe_failures == ()
    files = snapshot.portal_files
    assert files is not None
    assert files.variables_from == "user manager"
    assert files.desktops == ("ubuntu", "gnome")
    assert files.config_directories[1] == "/etc/xdg/xdg-ubuntu/xdg-desktop-portal"
    assert [c.path for c in files.configs] == ["/usr/share/xdg-desktop-portal/gnome-portals.conf"]


def test_inspect_routes_falls_back_to_the_shell_without_systemd() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW_USER, Outcome.NOT_FOUND, error="No such file"))
    runner.script("dpkg-query", "-W", "-f", DPKG_FORMAT, *PACKAGES, stdout="")
    show = ["systemctl", "--user", "--no-pager", "show"]
    show += [part for name in UNIT_PROPERTIES for part in ("-p", name)]
    runner.script_result(CommandResult((*show, *UNITS), Outcome.NOT_FOUND, error="No such file"))
    runner.script_result(
        CommandResult(
            ("busctl", "--user", "--no-pager", "--json=short", "call", "org.freedesktop.DBus",
             "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListActivatableNames"),
            Outcome.NOT_FOUND,
            error="No such file",
        )
    )  # fmt: skip
    read, list_dir = gnome_file_access()
    snapshot = inspect_routes(
        runner,
        environ={"XDG_CURRENT_DESKTOP": "GNOME", "HOME": "/home/u"},
        uid=1000,
        stat=_socket_stat,
        which=lambda name: None,
        exists=lambda path: False,
        read=read,
        list_dir=list_dir,
    )
    assert snapshot.portal_files is not None
    assert snapshot.portal_files.variables_from == "this shell"
    assert snapshot.portal_files.desktops == ("gnome",)


def test_inspect_all_and_diagnose_on_the_real_machine() -> None:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    snapshot = inspect_all(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
        read=read,
        list_dir=list_dir,
    )
    assert snapshot.probe_failures == ()
    assert snapshot.pipewire is not None
    assert snapshot.pipewire.version == "1.6.2"
    diagnosed = diagnose(snapshot)
    assert len(diagnosed.findings) == 15
    assert {f.status for f in diagnosed.findings} == {Status.PASS}
    assert all(f.layer is not None for f in diagnosed.findings)
