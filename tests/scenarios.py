"""Whole machines scripted into a FakeRunner, from the real captures in tests/fixtures."""

from __future__ import annotations

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
from tests.fakes import FakeRunner, read_fixture

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
