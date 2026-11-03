"""WLD-009: every default command is passive.

Each CLI command runs against the replayed real machine. Every command it issues must
match a read-only allowlist, no process may be spawned outside the (faked) runner, and
no file may be written: the report file named with --output is the only exception,
and it is tested separately.
"""

from __future__ import annotations

import builtins
import functools
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from screenshare_doctor import cli, orchestrator
from screenshare_doctor.privacy import RedactionContext
from tests.fakes import Call, FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine, stat_socket_or_dir

BUS_DAEMON = ("call", "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus")


def is_read_only(argv: Sequence[str]) -> bool:
    """Whether a command only reads state. The single place that defines "passive"."""
    program, args = argv[0], tuple(argv[1:])
    if program == "loginctl":
        return args[:2] in {("--no-pager", "show-user"), ("--no-pager", "show-session")}
    if program in {"dpkg-query", "rpm", "pacman"}:
        return args[:1] == {"dpkg-query": ("-W",), "rpm": ("-q",), "pacman": ("-Q",)}[program]
    if program == "systemctl":
        return args[:3] in {
            ("--user", "--no-pager", "show"),
            ("--user", "--no-pager", "show-environment"),
        }
    if program == "busctl":
        if args[:3] != ("--user", "--no-pager", "--json=short"):
            return False
        rest = args[3:]
        if rest[:4] == BUS_DAEMON:  # the bus daemon never starts a service to answer
            return rest[4] in {"ListActivatableNames", "NameHasOwner"}
        if rest[:1] != ("--auto-start=no",):
            return False
        verb = rest[1:2]
        if verb == ("call",):
            return rest[4:6] == ("org.freedesktop.DBus.Introspectable", "Introspect")
        return verb == ("get-property",)
    if program == "pw-dump":
        return args[:3] == ("-N", "-i", "0") and len(args) == 4 and not args[3].startswith("-")
    return False


@pytest.mark.parametrize(
    "argv",
    [
        ("systemctl", "--user", "start", "xdg-desktop-portal.service"),
        ("systemctl", "--user", "--no-pager", "restart", "pipewire.service"),
        ("busctl", "--user", "--no-pager", "--json=short", "call", "org.freedesktop.portal.Desktop",
         "/org/freedesktop/portal/desktop", "org.freedesktop.portal.ScreenCast", "CreateSession"),
        ("busctl", "--user", "--no-pager", "--json=short", "call", "org.freedesktop.DBus",
         "/org/freedesktop/DBus", "org.freedesktop.DBus", "StartServiceByName", "su", "x", "0"),
        ("pw-dump", "-N", "-i", "0", "-m"),
        ("loginctl", "--no-pager", "terminate-session", "2"),
        ("dpkg", "-i", "x.deb"),
        ("sh", "-c", "true"),
    ],
)  # fmt: skip
def test_the_allowlist_rejects_anything_that_acts(argv: tuple[str, ...]) -> None:
    assert not is_read_only(argv)


COMMANDS = [
    ("doctor",),
    ("doctor", "--format", "json", "--strict"),
    ("report",),
    ("report", "--format", "json"),
    ("troubleshoot", "screenshare", "--app", "firefox", "--symptom", "no-picker"),
    ("troubleshoot", "screenshare", "--symptom", "black-screen", "--explain"),
    ("check", "session"),
    ("check", "services"),
    ("check", "dbus"),
    ("check", "desktop"),
    ("routes", "explain", "ScreenCast"),
    ("rules", "list"),
]


@pytest.mark.parametrize("args", COMMANDS, ids=" ".join)
def test_every_command_is_passive(monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]) -> None:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    kwargs: dict[str, Any] = {
        "environ": read_env_fixture("gnome-wayland-ubuntu"),
        "uid": 1000,
        "stat": stat_socket_or_dir,
    }
    machine = kwargs | {
        "which": lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        "exists": lambda path: path == "/var/lib/dpkg/status",
    }
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(
        cli, "inspect_session", functools.partial(orchestrator.inspect_session, **kwargs)
    )
    monkeypatch.setattr(
        cli, "inspect_services", functools.partial(orchestrator.inspect_services, **machine)
    )
    files = machine | {"read": read, "list_dir": list_dir}
    monkeypatch.setattr(
        cli, "inspect_routes", functools.partial(orchestrator.inspect_routes, **files)
    )
    monkeypatch.setattr(cli, "inspect_all", functools.partial(orchestrator.inspect_all, **files))
    monkeypatch.setattr(cli, "installed_flatpaks", lambda ids, home: ())
    monkeypatch.setattr(RedactionContext, "current", classmethod(lambda cls: RedactionContext()))

    def no_process(*a: object, **k: object) -> None:
        raise AssertionError("a process was started outside the command runner")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    real_open = builtins.open

    def read_only_open(file: Any, mode: str = "r", *a: Any, **k: Any) -> Any:
        if any(flag in mode for flag in "wax+"):
            raise AssertionError(f"tried to write {file}")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(
        Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("write"))
    )
    monkeypatch.setattr(sys, "argv", ["screenshare-doctor", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code in (0, None), args
    calls: list[Call] = runner.calls
    if args[0] not in {"rules"}:
        assert calls, "the command ran no checks at all"
    for call in calls:
        assert is_read_only(call.argv), call.argv
