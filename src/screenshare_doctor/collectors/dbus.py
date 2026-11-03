"""The session bus, read without activating anything.

Every question goes either to the bus daemon itself (``org.freedesktop.DBus``: it never
starts a service to answer ``NameHasOwner`` or ``ListActivatableNames``) or, later, to a
name that already has an owner, with ``busctl --auto-start=no``. A portal that is not
running is therefore reported as not running instead of being started by the check.
"""

from __future__ import annotations

import json
from typing import Any

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
