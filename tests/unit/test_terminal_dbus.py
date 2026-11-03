"""The terminal D-Bus view."""

from __future__ import annotations

from rich.console import Console

from screenshare_doctor.collectors.dbus import FRONTEND, collect_dbus
from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    FailureKind,
    PortalObject,
    ProbeFailure,
    ScreenCastProperties,
    Snapshot,
)
from screenshare_doctor.reports.terminal import render_dbus
from tests.fakes import FakeRunner
from tests.scenarios import script_gnome_bus

GNOME = "org.freedesktop.impl.portal.desktop.gnome"


def _render(dbus: DbusFacts | None, *failures: ProbeFailure) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as capture:
        render_dbus(
            Snapshot(tool_version="0.1.0", created_at="x", dbus=dbus, probe_failures=failures),
            console,
        )
    return capture.get()


def _line(out: str, start: str) -> str:
    return next(line.rstrip() for line in out.splitlines() if line.startswith(start))


def test_real_gnome_bus() -> None:
    runner = FakeRunner()
    script_gnome_bus(runner)
    facts, _ = collect_dbus(runner)
    out = _render(facts)
    assert "Session bus reachable" in out
    frontend = _line(out, "portal frontend")
    assert "yes" in frontend
    assert frontend.endswith(
        "version 5; sources: monitor, window, virtual; cursor: hidden, embedded, metadata"
    )
    assert _line(out, "GTK backend").endswith("not implemented")
    assert _line(out, "KDE backend").split() == ["KDE", "backend", "no", "no", "-"]
    assert _line(out, "Mutter ScreenCast").endswith("version 4")
    assert "nothing was started" in out


def test_unreachable_bus() -> None:
    failure = ProbeFailure(
        "busctl ListActivatableNames",
        FailureKind.NONZERO_EXIT,
        "busctl exited with code 1: Failed to connect",
    )
    out = _render(DbusFacts(reachable=False), failure)
    assert "Session bus not reachable" in out
    assert "Component" not in out
    assert "busctl ListActivatableNames: busctl exited with code 1: Failed to connect" in out


def test_no_dbus_facts_at_all() -> None:
    assert "Session bus unknown" in _render(None)


def test_running_service_whose_introspection_failed() -> None:
    dbus = DbusFacts(
        reachable=True,
        names=(BusName(GNOME, running=True, activatable=True),),
        objects=(PortalObject(GNOME),),
    )
    assert _line(_render(dbus), "GNOME backend").endswith("unknown (see below)")


def test_screencast_with_limited_sources() -> None:
    dbus = DbusFacts(
        reachable=True,
        names=(BusName(FRONTEND, running=True, activatable=True),),
        objects=(
            PortalObject(
                FRONTEND,
                ("org.freedesktop.portal.ScreenCast",),
                ScreenCastProperties(version=4, source_types=1, cursor_modes=0),
            ),
        ),
    )
    assert _line(_render(dbus), "portal frontend").endswith(
        "version 4; sources: monitor; cursor: none"
    )


def test_unknown_running_state() -> None:
    dbus = DbusFacts(reachable=True, names=(BusName(GNOME, running=None, activatable=True),))
    assert _line(_render(dbus), "GNOME backend").split()[2:] == ["unknown", "yes", "-"]
