"""Desktop names from the session variables, read the way the portal reads them.

``XDG_CURRENT_DESKTOP`` is a colon-separated list, most specific first: Ubuntu sets
``ubuntu:GNOME``, Budgie ``Budgie:GNOME``. Since portals.conf support (1.17),
xdg-desktop-portal keeps only entries made of ASCII letters, digits, ``-`` and ``_``,
because it builds file names from them, and lower-cases those (``g_ascii_tolower``) to
find ``<name>-portals.conf``. :func:`parse_desktop_list` does exactly that and also
returns the entries the portal ignores, so a report can point at them.

Pure functions: nothing here reads the environment or files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_VALID_NAME = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)


class DesktopFamily(StrEnum):
    """Which group of desktop expectations applies.

    ``GNOME``, ``KDE`` and ``HYPRLAND`` have their own rule bundles; ``WLROOTS`` covers
    the compositors that share xdg-desktop-portal-wlr. ``OTHER`` is a known desktop
    without a bundle, ``UNKNOWN`` means no name was recognised.
    """

    GNOME = "gnome"
    KDE = "kde"
    HYPRLAND = "hyprland"
    WLROOTS = "wlroots"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DesktopList:
    """``names``: what the portal uses, in order. ``ignored``: entries it drops, as found."""

    names: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()


def ascii_lower(text: str) -> str:
    """Lower-case A-Z only, like GLib's ``g_ascii_tolower``."""
    return text.translate(_ASCII_LOWER)


def parse_desktop_list(raw: str | None) -> DesktopList:
    """Split ``XDG_CURRENT_DESKTOP`` into the names the portal uses and the ones it ignores.

    Empty entries (``::GNOME``) are dropped silently, as the portal drops them; anything
    else that is not a valid name is listed in ``ignored``.
    """
    if raw is None:
        return DesktopList()
    names: list[str] = []
    ignored: list[str] = []
    for entry in raw.split(":"):
        if _VALID_NAME.fullmatch(entry):
            names.append(ascii_lower(entry))
        elif entry:
            ignored.append(entry)
    return DesktopList(tuple(names), tuple(ignored))
