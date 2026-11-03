"""The terminal route explanation (WLD-005)."""

from __future__ import annotations

import os
import stat

from rich.console import Console

from screenshare_doctor.models import (
    PackageFacts,
    PackageInfo,
    PackageState,
    PortalDescriptor,
    PortalFiles,
    PortalsConf,
    Snapshot,
)
from screenshare_doctor.orchestrator import inspect_routes
from screenshare_doctor.reports.terminal import render_route
from screenshare_doctor.routes import RouteKind
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine

SC = "org.freedesktop.impl.portal.ScreenCast"


def _render(snapshot: Snapshot, interface: str = SC) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as capture:
        render_route(snapshot, interface, console)
    return capture.get()


def _socket_stat(path: str) -> os.stat_result:
    return os.stat_result((stat.S_IFSOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0))


def _real_snapshot(extra: dict[str, bytes] | None = None) -> Snapshot:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access(extra)
    return inspect_routes(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=_socket_stat,
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
        read=read,
        list_dir=list_dir,
    )


def test_real_gnome_machine() -> None:
    out = _render(_real_snapshot())
    assert "Interface   ScreenCast (org.freedesktop.portal.ScreenCast)" in out
    assert "Predicted   gnome (org.freedesktop.impl.portal.desktop.gnome)" in out
    assert (
        "Decided by  default=gnome;gtk in /usr/share/xdg-desktop-portal/gnome-portals.conf" in out
    )
    assert "xdg-desktop-portal 1.21.1+ds-1ubuntu3.1 (selection rules of 1.21.1 and later" in out
    assert "Desktops    ubuntu, gnome (XDG_CURRENT_DESKTOP of the user manager)" in out
    assert "On D-Bus    gnome is running and implements it; the frontend offers it" in out
    assert " 1. /home/user/.config/xdg-desktop-portal: nothing" in out
    assert "11. /usr/share/xdg-desktop-portal: gnome-portals.conf" in out
    assert "may be wrong" not in out


def test_user_override_that_names_a_missing_backend() -> None:
    # The classic mistake: copying a Hyprland portals.conf onto a GNOME machine.
    snapshot = _real_snapshot(
        {
            "/home/user/.config/xdg-desktop-portal/portals.conf": (
                b"[preferred]\ndefault=hyprland;gtk\n"
            )
        }
    )
    out = _render(snapshot)
    assert (
        "Decided by  default=gnome;gtk in /usr/share/xdg-desktop-portal/gnome-portals.conf" in out
    )
    assert "hyprland is listed but not installed" in out
    assert "gtk does not implement org.freedesktop.impl.portal.ScreenCast" in out
    assert " 1. /home/user/.config/xdg-desktop-portal: portals.conf" in out


def test_user_override_that_disables_screencast() -> None:
    snapshot = _real_snapshot(
        {
            "/home/user/.config/xdg-desktop-portal/gnome-portals.conf": (
                b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"
            )
        }
    )
    out = _render(snapshot)
    assert "Predicted   none: a configuration disables this interface" in out
    assert (
        "Decided by  org.freedesktop.impl.portal.ScreenCast=none in "
        "/home/user/.config/xdg-desktop-portal/gnome-portals.conf"
    ) in out


def test_ignored_user_file_is_shown() -> None:
    snapshot = _real_snapshot(
        {"/home/user/.config/xdg-desktop-portal/gnome-portals.conf": b"default=kde\n"}
    )
    out = _render(snapshot)
    assert "gnome-portals.conf (ignored: unreadable: line 1: key before the first group)" in out
    assert "Predicted   gnome" in out


def test_interface_nobody_implements() -> None:
    out = _render(_real_snapshot(), "org.freedesktop.impl.portal.Camera")
    assert "Predicted   none: no installed backend implements it" in out
    assert "Decided by  nothing" in out


def test_unknown_version_and_shell_variables() -> None:
    gnome = PortalDescriptor(
        "gnome",
        "/usr/share/xdg-desktop-portal/portals/gnome.portal",
        "org.freedesktop.impl.portal.desktop.gnome",
        (SC,),
        ("gnome",),
    )
    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="x",
        portal_files=PortalFiles(
            desktops=("gnome",), descriptors=(gnome,), variables_from="this shell"
        ),
    )
    out = _render(snapshot)
    assert "version unknown; the newest rules" in out
    assert "(XDG_CURRENT_DESKTOP of this shell)" in out
    assert "UseIn" in out
    assert "The prediction may be wrong because:" in out
    assert "On D-Bus    not checked" in out


def test_older_portal_rules_are_named() -> None:
    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="x",
        packages=PackageFacts(
            "dpkg", (PackageInfo("xdg-desktop-portal", PackageState.INSTALLED, "1.18.4-1"),)
        ),
        portal_files=PortalFiles(
            desktops=("gnome",),
            configs=(
                PortalsConf(
                    "/usr/share/xdg-desktop-portal/portals.conf", (("default", ("gnome",)),)
                ),
            ),
        ),
    )
    assert "(selection rules of 1.17 and 1.18; read as 1.18.4)" in _render(snapshot)


def test_render_returns_the_route() -> None:
    console = Console(width=200, color_system=None)
    with console.capture():
        route = render_route(_real_snapshot(), SC, console)
    assert route.kind is RouteKind.BACKEND
