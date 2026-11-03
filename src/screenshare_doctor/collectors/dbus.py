"""The session bus, read without activating anything.

Every question goes either to the bus daemon itself (``org.freedesktop.DBus``: it never
starts a service to answer ``NameHasOwner`` or ``ListActivatableNames``) or, later, to a
name that already has an owner, with ``busctl --auto-start=no``. A portal that is not
running is therefore reported as not running instead of being started by the check.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    FailureKind,
    ProbeFailure,
    ScreenCastProperties,
)
from screenshare_doctor.runner import CommandRunner, probe_failure

FRONTEND = "org.freedesktop.portal.Desktop"

BUS_NAMES: tuple[str, ...] = (
    FRONTEND,
    "org.freedesktop.impl.portal.desktop.gnome",
    "org.freedesktop.impl.portal.desktop.gtk",
    "org.freedesktop.impl.portal.desktop.kde",
    "org.freedesktop.impl.portal.desktop.wlr",
    "org.freedesktop.impl.portal.desktop.hyprland",
    "org.gnome.Mutter.ScreenCast",
)
"""The frontend, the backends, and GNOME's compositor-side screen-cast service, which the
GNOME backend calls. KDE and Hyprland offer theirs through Wayland protocols instead."""


PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"
IMPL_SCREENCAST = "org.freedesktop.impl.portal.ScreenCast"
SCREENCAST_PROPERTIES = ("version", "AvailableSourceTypes", "AvailableCursorModes")

_INTERFACE = re.compile(r"<interface\s+name=\"([^\"]+)\"")
_PORTAL_INTERFACE_PREFIXES = (
    "org.freedesktop.portal.",
    "org.freedesktop.impl.portal.",
    "org.freedesktop.host.portal.",
)


class BusctlOutputError(ValueError):
    """busctl printed something that is not the JSON it promises with ``--json=short``."""


def parse_busctl_json(text: str) -> list[Any]:
    """The JSON documents busctl prints, one per line (``get-property`` with several
    properties prints several)."""
    documents: list[Any] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            document = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BusctlOutputError(f"not JSON: {exc.msg}") from None
        if not isinstance(document, dict) or "data" not in document:
            raise BusctlOutputError("a JSON document without data")
        documents.append(document)
    if not documents:
        raise BusctlOutputError("no output")
    return documents


def parse_bool_reply(text: str) -> bool:
    """The answer of a method returning one boolean, such as ``NameHasOwner``."""
    document = parse_busctl_json(text)[0]
    data = document["data"]
    if document.get("type") != "b" or not isinstance(data, list) or len(data) != 1:
        raise BusctlOutputError("expected one boolean")
    if not isinstance(data[0], bool):
        raise BusctlOutputError("expected one boolean")
    return data[0]


def parse_string_list_reply(text: str) -> list[str]:
    """The answer of a method returning one string array, such as ``ListActivatableNames``."""
    document = parse_busctl_json(text)[0]
    data = document["data"]
    if document.get("type") != "as" or not isinstance(data, list) or len(data) != 1:
        raise BusctlOutputError("expected one string array")
    names = data[0]
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise BusctlOutputError("expected one string array")
    return names


def parse_introspection(text: str) -> tuple[str, ...]:
    """The portal interfaces named in an ``Introspect`` reply, sorted, without duplicates.

    The XML is not parsed as XML: only ``<interface name="…">`` is needed, and a
    regular expression cannot be made to expand entities.
    """
    document = parse_busctl_json(text)[0]
    data = document["data"]
    if document.get("type") != "s" or not isinstance(data, list) or len(data) != 1:
        raise BusctlOutputError("expected one string")
    if not isinstance(data[0], str):
        raise BusctlOutputError("expected one string")
    names = {
        name for name in _INTERFACE.findall(data[0]) if name.startswith(_PORTAL_INTERFACE_PREFIXES)
    }
    return tuple(sorted(names))


def parse_screencast_properties(text: str) -> ScreenCastProperties:
    """``get-property … version AvailableSourceTypes AvailableCursorModes``: three lines."""
    documents = parse_busctl_json(text)
    if len(documents) != len(SCREENCAST_PROPERTIES):
        raise BusctlOutputError(f"expected {len(SCREENCAST_PROPERTIES)} properties")
    values = [_unsigned(document) for document in documents]
    return ScreenCastProperties(*values)


def parse_integer_property(text: str) -> int:
    """One integer property, such as Mutter's ScreenCast ``Version`` (type ``i``)."""
    return _unsigned(parse_busctl_json(text)[0])


def _unsigned(document: dict[str, Any]) -> int:
    data = document["data"]
    if (
        document.get("type") not in {"u", "i"}
        or isinstance(data, bool)
        or not isinstance(data, int)
    ):
        raise BusctlOutputError("expected an integer property")
    if data < 0:
        raise BusctlOutputError("expected a non-negative integer")
    return data


BUSCTL_TIMEOUT = 5.0
"""Seconds; a healthy bus answers in milliseconds, a stuck one never does."""

BUSCTL = ("busctl", "--user", "--no-pager", "--json=short")
_BUS_DAEMON = ("call", "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus")


def collect_bus_names(
    runner: CommandRunner, *, names: Sequence[str] = BUS_NAMES
) -> tuple[DbusFacts, tuple[ProbeFailure, ...]]:
    """Ask the bus daemon which of ``names`` are running and which it could start.

    ``ListActivatableNames`` goes first and doubles as the reachability check: if the
    session bus does not answer it, nothing else is asked. Only the requested names
    are kept from the list; the rest (installed apps, for one) is discarded.
    """
    result = runner.run([*BUSCTL, *_BUS_DAEMON, "ListActivatableNames"], timeout=BUSCTL_TIMEOUT)
    failure = probe_failure("busctl ListActivatableNames", result)
    if failure is not None:
        # busctl exits non-zero when it cannot connect; a missing busctl or a timeout
        # says nothing about the bus itself.
        reachable = False if failure.kind is FailureKind.NONZERO_EXIT else None
        return DbusFacts(reachable=reachable), (failure,)
    try:
        activatable = set(parse_string_list_reply(result.stdout))
    except BusctlOutputError as exc:
        failure = ProbeFailure(
            "busctl ListActivatableNames", FailureKind.MALFORMED_OUTPUT, str(exc)
        )
        return DbusFacts(reachable=True), (failure,)

    failures: list[ProbeFailure] = []
    found: list[BusName] = []
    for name in names:
        running, failure = _has_owner(runner, name)
        if failure is not None:
            failures.append(failure)
        found.append(BusName(name, running=running, activatable=name in activatable))
        if failure is not None and failure.kind is not FailureKind.MALFORMED_OUTPUT:
            # The same command would fail the same way for every other name.
            found += [
                BusName(rest, activatable=rest in activatable) for rest in names[len(found) :]
            ]
            break
    return DbusFacts(reachable=True, names=tuple(found)), tuple(failures)


def _has_owner(runner: CommandRunner, name: str) -> tuple[bool | None, ProbeFailure | None]:
    result = runner.run([*BUSCTL, *_BUS_DAEMON, "NameHasOwner", "s", name], timeout=BUSCTL_TIMEOUT)
    failure = probe_failure("busctl NameHasOwner", result)
    if failure is not None:
        return None, failure
    try:
        return parse_bool_reply(result.stdout), None
    except BusctlOutputError as exc:
        return None, ProbeFailure("busctl NameHasOwner", FailureKind.MALFORMED_OUTPUT, str(exc))
