"""Reading the running portal services without starting any (WLD-004)."""

from __future__ import annotations

from screenshare_doctor.collectors.dbus import (
    BUS_NAMES,
    FRONTEND,
    IMPL_SCREENCAST,
    MUTTER_SCREENCAST,
    collect_dbus,
    collect_portal_objects,
)
from screenshare_doctor.models import BusName, FailureKind, PortalObject, ScreenCastProperties
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_fixture
from tests.scenarios import (
    BUS_DAEMON,
    GNOME_RUNNING,
    introspect,
    screencast_properties,
    script_gnome_bus,
)

GNOME = "org.freedesktop.impl.portal.desktop.gnome"
GTK = "org.freedesktop.impl.portal.desktop.gtk"
FULL = ScreenCastProperties(version=5, source_types=7, cursor_modes=7)


def test_real_gnome_session() -> None:
    runner = FakeRunner()
    script_gnome_bus(runner)
    facts, failures = collect_dbus(runner)
    assert failures == ()
    objects = {o.name: o for o in facts.objects}
    assert set(objects) == set(GNOME_RUNNING)
    assert objects[FRONTEND].screencast == FULL
    assert objects[GNOME].screencast == FULL
    assert objects[GNOME].interfaces is not None
    assert IMPL_SCREENCAST in objects[GNOME].interfaces
    assert objects[GTK].screencast is None  # no ScreenCast in the gtk backend
    assert objects[MUTTER_SCREENCAST] == PortalObject(
        MUTTER_SCREENCAST, screencast=ScreenCastProperties(version=4)
    )


def test_passive_harness_on_the_real_session() -> None:
    """The WLD-004 promise: services are only contacted when already running, never started."""
    runner = FakeRunner()
    script_gnome_bus(runner)
    facts, _ = collect_dbus(runner)
    running = {n.name for n in facts.names if n.running}
    for call in runner.calls:
        argv = call.argv
        if argv[: len(BUS_DAEMON)] == BUS_DAEMON:
            continue  # the bus daemon never starts a service to answer
        assert "--auto-start=no" in argv, argv
        target = argv[argv.index("--auto-start=no") + 2]
        assert target in running, argv


def test_stopped_names_are_never_contacted() -> None:
    names = [BusName(name, running=False, activatable=True) for name in BUS_NAMES]
    runner = FakeRunner()
    objects, failures = collect_portal_objects(runner, names)
    assert (objects, failures) == ((), ())
    assert runner.calls == []


def test_unknown_running_state_is_not_contacted_either() -> None:
    runner = FakeRunner()
    objects, _ = collect_portal_objects(runner, [BusName(FRONTEND, running=None)])
    assert objects == ()
    assert runner.calls == []


def test_name_that_disappeared_is_a_failure_not_a_start() -> None:
    runner = FakeRunner()
    runner.script(
        *introspect(GNOME),
        stderr=f"Call failed: The name {GNOME} was not provided by any .service files",
        returncode=1,
    )
    objects, failures = collect_portal_objects(runner, [BusName(GNOME, running=True)])
    assert objects == (PortalObject(GNOME),)
    assert failures[0].kind is FailureKind.NONZERO_EXIT


def test_property_read_failure_keeps_the_interfaces() -> None:
    runner = FakeRunner()
    runner.script(
        *introspect(GNOME), stdout=read_fixture("busctl", "introspect-gnome-backend.json")
    )
    runner.script_result(CommandResult(screencast_properties(GNOME), Outcome.TIMEOUT, duration=5.0))
    objects, failures = collect_portal_objects(runner, [BusName(GNOME, running=True)])
    assert objects[0].interfaces is not None
    assert objects[0].screencast is None
    assert failures[0].kind is FailureKind.TIMEOUT


def test_malformed_replies_are_recorded() -> None:
    runner = FakeRunner()
    runner.script(*introspect(GNOME), stdout="<node/>\n")
    runner.script(*introspect(GTK), stdout=read_fixture("busctl", "introspect-gnome-backend.json"))
    runner.script(*screencast_properties(GTK), stdout='{"type":"u","data":5}\n')
    objects, failures = collect_portal_objects(
        runner, [BusName(GNOME, running=True), BusName(GTK, running=True)]
    )
    assert [f.kind for f in failures] == [FailureKind.MALFORMED_OUTPUT] * 2
    assert objects[0] == PortalObject(GNOME)
    assert objects[1].screencast is None


def test_unreachable_bus_asks_no_service() -> None:
    runner = FakeRunner()
    runner.script(*BUS_DAEMON, "ListActivatableNames", stderr="Failed to connect", returncode=1)
    facts, failures = collect_dbus(runner)
    assert facts.reachable is False
    assert facts.objects == ()
    assert len(runner.calls) == 1
    assert len(failures) == 1
