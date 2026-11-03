"""Asking the bus daemon about the portal names (WLD-004)."""

from __future__ import annotations

from screenshare_doctor.collectors.dbus import (
    BUS_NAMES,
    BUSCTL_TIMEOUT,
    FRONTEND,
    collect_bus_names,
)
from screenshare_doctor.models import BusName, DbusFacts, FailureKind
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_fixture

DAEMON = (
    "busctl",
    "--user",
    "--no-pager",
    "--json=short",
    "call",
    "org.freedesktop.DBus",
    "/org/freedesktop/DBus",
    "org.freedesktop.DBus",
)
LIST = (*DAEMON, "ListActivatableNames")
RUNNING_HERE = {
    FRONTEND,
    "org.freedesktop.impl.portal.desktop.gnome",
    "org.freedesktop.impl.portal.desktop.gtk",
    "org.gnome.Mutter.ScreenCast",
}


def has_owner(name: str) -> tuple[str, ...]:
    return (*DAEMON, "NameHasOwner", "s", name)


def _gnome_runner() -> FakeRunner:
    runner = FakeRunner()
    runner.script(*LIST, stdout=read_fixture("busctl", "list-activatable-ubuntu-gnome.json"))
    for name in BUS_NAMES:
        reply = "name-has-owner-true.json" if name in RUNNING_HERE else "name-has-owner-false.json"
        runner.script(*has_owner(name), stdout=read_fixture("busctl", reply))
    return runner


def test_real_ubuntu_gnome_bus() -> None:
    runner = _gnome_runner()
    facts, failures = collect_bus_names(runner)
    assert failures == ()
    assert facts.reachable is True
    by_name = {n.name: n for n in facts.names}
    assert by_name[FRONTEND] == BusName(FRONTEND, running=True, activatable=True)
    kde = "org.freedesktop.impl.portal.desktop.kde"
    assert by_name[kde] == BusName(kde, running=False, activatable=False)
    # Mutter's screen-cast service is owned by gnome-shell, not started from a file.
    mutter = by_name["org.gnome.Mutter.ScreenCast"]
    assert (mutter.running, mutter.activatable) == (True, False)
    assert all(call.timeout == BUSCTL_TIMEOUT for call in runner.calls)


def test_only_the_bus_daemon_is_asked() -> None:
    runner = _gnome_runner()
    collect_bus_names(runner)
    for call in runner.calls:
        assert call.argv[:8] == DAEMON
        assert call.argv[8] in {"ListActivatableNames", "NameHasOwner"}


def test_unreachable_bus_stops_after_one_command() -> None:
    runner = FakeRunner()
    runner.script(
        *LIST,
        stderr="Failed to connect to user scope bus via local transport: No such file or directory",
        returncode=1,
    )
    facts, failures = collect_bus_names(runner)
    assert facts == DbusFacts(reachable=False)
    assert "Failed to connect" in failures[0].detail
    assert len(runner.calls) == 1


def test_missing_busctl_leaves_the_bus_unknown() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(LIST, Outcome.NOT_FOUND, error="No such file"))
    facts, failures = collect_bus_names(runner)
    assert facts == DbusFacts(reachable=None)
    assert failures[0].kind is FailureKind.NOT_FOUND


def test_malformed_activatable_list() -> None:
    runner = FakeRunner()
    runner.script(*LIST, stdout="garbage\n")
    facts, failures = collect_bus_names(runner)
    assert facts.reachable is True
    assert facts.names == ()
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT


def test_timeout_on_one_name_stops_the_rest() -> None:
    runner = FakeRunner()
    runner.script(*LIST, stdout='{"type":"as","data":[["org.freedesktop.portal.Desktop"]]}\n')
    runner.script(*has_owner(FRONTEND), stdout=read_fixture("busctl", "name-has-owner-true.json"))
    runner.script_result(
        CommandResult(has_owner(BUS_NAMES[1]), Outcome.TIMEOUT, duration=BUSCTL_TIMEOUT)
    )
    facts, failures = collect_bus_names(runner)
    assert [f.kind for f in failures] == [FailureKind.TIMEOUT]
    assert len(facts.names) == len(BUS_NAMES)
    assert facts.names[0].running is True
    assert all(name.running is None for name in facts.names[1:])
    assert len(runner.calls) == 3


def test_malformed_reply_for_one_name_does_not_stop_the_rest() -> None:
    runner = _gnome_runner()
    runner.script(*has_owner(BUS_NAMES[2]), stdout='{"type":"s","data":["?"]}\n')
    facts, failures = collect_bus_names(runner)
    assert [f.kind for f in failures] == [FailureKind.MALFORMED_OUTPUT]
    assert facts.names[2].running is None
    assert facts.names[3].running is False


def test_other_activatable_names_are_not_kept() -> None:
    facts, _ = collect_bus_names(_gnome_runner())
    assert "org.gnome.Shell.Extensions" not in repr(facts)
