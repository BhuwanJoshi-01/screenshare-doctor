"""The terminal services view."""

from __future__ import annotations

from rich.console import Console

from screenshare_doctor.collectors.packages import parse_dpkg
from screenshare_doctor.collectors.services import parse_activation_environment, parse_units
from screenshare_doctor.models import (
    FailureKind,
    PackageFacts,
    PackageInfo,
    PackageState,
    ProbeFailure,
    ServiceFacts,
    SessionEnvironment,
    SessionFacts,
    Snapshot,
    UserService,
)
from screenshare_doctor.reports.terminal import render_services
from tests.fakes import read_fixture

SHELL = SessionEnvironment(
    session_type="wayland",
    current_desktop="ubuntu:GNOME",
    wayland_display="wayland-0",
    display=":0",
)


def _render(snapshot: Snapshot) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as capture:
        render_services(snapshot, console)
    return capture.get()


def _real_snapshot() -> Snapshot:
    return Snapshot(
        tool_version="0.1.0",
        created_at="2026-11-03T10:00:00Z",
        session=SessionFacts(environment=SHELL),
        packages=PackageFacts(
            "dpkg",
            parse_dpkg(
                read_fixture("packages", "dpkg-ubuntu-gnome.stdout"),
                read_fixture("packages", "dpkg-ubuntu-gnome.stderr"),
            ),
        ),
        services=ServiceFacts(
            parse_units(read_fixture("systemctl", "show-units-ubuntu-gnome.txt")),
            parse_activation_environment(
                read_fixture("systemctl", "show-environment-ubuntu-gnome.txt")
            ),
        ),
    )


def _line(out: str, start: str) -> str:
    return next(line.rstrip() for line in out.splitlines() if line.startswith(start))


def test_real_ubuntu_gnome_stack() -> None:
    out = _render(_real_snapshot())
    assert "1.21.1+ds-1ubuntu3.1" in _line(out, "portal frontend")
    assert "running (static)" in _line(out, "portal frontend")
    assert "50.0-0ubuntu1" in _line(out, "GNOME backend")
    assert "not installed" in _line(out, "KDE backend")
    assert "no unit" in _line(out, "KDE backend")
    pipewire = _line(out, "PipeWire")
    assert "socket: running (enabled); service: running (enabled)" in pipewire
    assert "Packages from dpkg." in out
    assert "XDG_CURRENT_DESKTOP  ubuntu:GNOME  (same as this shell)" in out
    assert "WAYLAND_DISPLAY      wayland-0     (same as this shell)" in out


def test_activation_environment_that_differs_from_the_shell() -> None:
    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="2026-11-03T10:00:00Z",
        session=SessionFacts(
            environment=SessionEnvironment(current_desktop="Hyprland", wayland_display="wayland-1")
        ),
        services=ServiceFacts(services=(), activation_environment=SessionEnvironment()),
    )
    out = _render(snapshot)
    assert "XDG_CURRENT_DESKTOP  unset  (this shell: Hyprland)" in out
    assert "WAYLAND_DISPLAY      unset  (this shell: wayland-1)" in out


def test_no_comparison_outside_the_desktop() -> None:
    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="2026-11-03T10:00:00Z",
        session=SessionFacts(environment=SessionEnvironment(ssh=True)),
        services=ServiceFacts(services=(), activation_environment=SHELL),
    )
    out = _render(snapshot)
    assert "XDG_CURRENT_DESKTOP  ubuntu:GNOME\n" in out
    assert "this shell" not in out


def test_unit_states() -> None:
    services = (
        UserService("xdg-desktop-portal.service", "loaded", "failed", "failed", "static"),
        UserService("xdg-desktop-portal-gnome.service", "loaded", "inactive", "dead", "static"),
        UserService("xdg-desktop-portal-gtk.service", "masked", "inactive", "dead", "masked"),
        UserService("wireplumber.service", "loaded", "activating", "start", "enabled"),
    )
    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="2026-11-03T10:00:00Z",
        services=ServiceFacts(services=services),
    )
    out = _render(snapshot)
    assert _line(out, "portal frontend").endswith("failed")
    assert _line(out, "GNOME backend").endswith("not running")
    assert _line(out, "GTK backend").endswith("masked")
    assert _line(out, "WirePlumber").endswith("activating")
    assert _line(out, "KDE backend").endswith("unknown")


def test_package_states_and_files_fallback() -> None:
    packages = PackageFacts(
        "files",
        (
            PackageInfo("xdg-desktop-portal", PackageState.INSTALLED),
            PackageInfo("pipewire", PackageState.BROKEN, "1.4.9-1"),
        ),
    )
    snapshot = Snapshot(tool_version="0.1.0", created_at="x", packages=packages)
    out = _render(snapshot)
    assert "installed" in _line(out, "portal frontend")
    assert "broken install (1.4.9-1)" in _line(out, "PipeWire")
    assert "unknown" in _line(out, "GNOME backend")
    assert "unknown may mean not installed" in out


def test_nothing_collected_lists_the_failures() -> None:
    failure = ProbeFailure(
        "systemctl --user show", FailureKind.NOT_FOUND, "systemctl was not found"
    )
    out = _render(Snapshot(tool_version="0.1.0", created_at="x", probe_failures=(failure,)))
    assert "not read (see below)" in out
    assert "systemctl --user show: systemctl was not found" in out
    assert all(_line(out, label).endswith("unknown") for label in ("portal frontend", "PipeWire"))
