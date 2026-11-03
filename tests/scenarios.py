"""Whole machines scripted into a FakeRunner, from the real captures in tests/fixtures."""

from __future__ import annotations

from collections.abc import Callable

from screenshare_doctor.collectors.dbus import (
    BUS_NAMES,
    BUSCTL,
    FRONTEND,
    IMPL_SCREENCAST,
    MUTTER_SCREENCAST,
    NO_AUTO_START,
    PORTAL_PATH,
    SCREENCAST,
    SCREENCAST_PROPERTIES,
)
from screenshare_doctor.collectors.logind import SESSION_PROPERTIES
from screenshare_doctor.collectors.packages import DPKG_FORMAT, PACKAGES
from screenshare_doctor.collectors.services import UNIT_PROPERTIES, UNITS
from tests.fakes import FIXTURES, FakeRunner, read_fixture

BUS_DAEMON = (
    *BUSCTL,
    "call",
    "org.freedesktop.DBus",
    "/org/freedesktop/DBus",
    "org.freedesktop.DBus",
)

GNOME_RUNNING = (
    FRONTEND,
    "org.freedesktop.impl.portal.desktop.gnome",
    "org.freedesktop.impl.portal.desktop.gtk",
    MUTTER_SCREENCAST,
)
"""The names that had an owner on the Ubuntu 26.04 GNOME 50.1 machine."""


def introspect(name: str) -> tuple[str, ...]:
    return (
        *NO_AUTO_START,
        "call",
        name,
        PORTAL_PATH,
        "org.freedesktop.DBus.Introspectable",
        "Introspect",
    )


def screencast_properties(name: str) -> tuple[str, ...]:
    interface = SCREENCAST if name == FRONTEND else IMPL_SCREENCAST
    return (*NO_AUTO_START, "get-property", name, PORTAL_PATH, interface, *SCREENCAST_PROPERTIES)


MUTTER_VERSION = (
    *NO_AUTO_START,
    "get-property",
    MUTTER_SCREENCAST,
    "/org/gnome/Mutter/ScreenCast",
    MUTTER_SCREENCAST,
    "Version",
)


def script_gnome_bus(runner: FakeRunner) -> None:
    """Every busctl reply of the real GNOME session."""
    runner.script(
        *BUS_DAEMON,
        "ListActivatableNames",
        stdout=read_fixture("busctl", "list-activatable-ubuntu-gnome.json"),
    )
    for name in BUS_NAMES:
        reply = "name-has-owner-true.json" if name in GNOME_RUNNING else "name-has-owner-false.json"
        runner.script(*BUS_DAEMON, "NameHasOwner", "s", name, stdout=read_fixture("busctl", reply))
    runner.script(
        *introspect(FRONTEND),
        stdout=read_fixture("busctl", "introspect-frontend-ubuntu-gnome.json"),
    )
    runner.script(
        *introspect("org.freedesktop.impl.portal.desktop.gnome"),
        stdout=read_fixture("busctl", "introspect-gnome-backend.json"),
    )
    runner.script(
        *introspect("org.freedesktop.impl.portal.desktop.gtk"),
        stdout=read_fixture("busctl", "introspect-gtk-backend.json"),
    )
    runner.script(
        *screencast_properties(FRONTEND),
        stdout=read_fixture("busctl", "screencast-props-frontend.json"),
    )
    runner.script(
        *screencast_properties("org.freedesktop.impl.portal.desktop.gnome"),
        stdout=read_fixture("busctl", "screencast-props-gnome-backend.json"),
    )
    runner.script(*MUTTER_VERSION, stdout=read_fixture("busctl", "mutter-screencast-version.json"))


def script_gnome_machine(runner: FakeRunner, *, uid: int) -> None:
    """Every command of the real Ubuntu 26.04 GNOME machine: logind, dpkg, systemd, D-Bus."""
    runner.script(
        "loginctl", "--no-pager", "show-user", str(uid), "-p", "Display",
        stdout=read_fixture("loginctl", "show-user-display-gnome.txt"),
    )  # fmt: skip
    show_session = ["loginctl", "--no-pager", "show-session", "63"]
    show_session += [part for name in SESSION_PROPERTIES for part in ("-p", name)]
    runner.script(*show_session, stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt"))
    runner.script(
        "dpkg-query", "-W", "-f", DPKG_FORMAT, *PACKAGES,
        stdout=read_fixture("packages", "dpkg-ubuntu-gnome.stdout"),
        stderr=read_fixture("packages", "dpkg-ubuntu-gnome.stderr"),
        returncode=1,
    )  # fmt: skip
    show = ["systemctl", "--user", "--no-pager", "show"]
    show += [part for name in UNIT_PROPERTIES for part in ("-p", name)]
    runner.script(*show, *UNITS, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script(
        "systemctl", "--user", "--no-pager", "show-environment",
        stdout=read_fixture("systemctl", "show-environment-ubuntu-gnome.txt"),
    )  # fmt: skip
    script_gnome_bus(runner)
    script_gnome_pipewire(runner)


PW_DUMP_FIXTURES = {
    "PipeWire:Interface:Core": "pw-dump-core-ubuntu.json",
    "PipeWire:Interface:Client": "pw-dump-clients-ubuntu.json",
    "PipeWire:Interface:Node": "pw-dump-nodes-ubuntu.json",
}


def script_gnome_pipewire(runner: FakeRunner) -> None:
    """The reduced real pw-dump answers of the GNOME machine."""
    for object_type, fixture in PW_DUMP_FIXTURES.items():
        runner.script(
            "pw-dump", "-N", "-i", "0", object_type, stdout=read_fixture("pipewire", fixture)
        )


GNOME_PORTAL_FILES = {
    "/usr/share/xdg-desktop-portal/gnome-portals.conf": "gnome-portals.conf",
    "/usr/share/xdg-desktop-portal/portals/gnome.portal": "gnome.portal",
    "/usr/share/xdg-desktop-portal/portals/gtk.portal": "gtk.portal",
    "/usr/share/xdg-desktop-portal/portals/gnome-keyring.portal": "gnome-keyring.portal",
}
"""The portal files of the real machine, by path, and their fixtures."""


def gnome_file_access(
    extra: dict[str, bytes] | None = None,
) -> tuple[Callable[[str], bytes | None], Callable[[str], tuple[str, ...]]]:
    """``read`` and ``list_dir`` functions that see the real machine's portal files only."""
    files = {
        path: (FIXTURES / "portals" / name).read_bytes()
        for path, name in GNOME_PORTAL_FILES.items()
    }
    files.update(extra or {})

    def read(path: str) -> bytes | None:
        return files.get(path)

    def list_dir(directory: str) -> tuple[str, ...]:
        prefix = directory.rstrip("/") + "/"
        return tuple(
            sorted(
                path[len(prefix) :]
                for path in files
                if path.startswith(prefix)
                and "/" not in path[len(prefix) :]
                and path.endswith(".portal")
            )
        )

    return read, list_dir
