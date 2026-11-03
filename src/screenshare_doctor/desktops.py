"""Desktop names from the session variables, read the way the portal reads them.

``XDG_CURRENT_DESKTOP`` is a colon-separated list, most specific first: Ubuntu sets
``ubuntu:GNOME``, Budgie ``Budgie:GNOME``. Since portals.conf support (1.17),
xdg-desktop-portal keeps only entries made of ASCII letters, digits, ``-`` and ``_``,
because it builds file names from them, and lower-cases those (``g_ascii_tolower``) to
find ``<name>-portals.conf``. :func:`parse_desktop_list` does exactly that and also
returns the entries the portal ignores, so a report can point at them.

:func:`identify_desktop` then names the desktop family from the first entry it knows,
and only falls back to the session name (``XDG_SESSION_DESKTOP``, ``DESKTOP_SESSION``)
when ``XDG_CURRENT_DESKTOP`` names nothing it knows; the result says which variable
the answer came from.

Pure functions: nothing here reads the environment or files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from screenshare_doctor.models import SessionEnvironment

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


_F = DesktopFamily

DESKTOP_FAMILIES: dict[str, DesktopFamily] = {
    "gnome": _F.GNOME,
    "gnome-classic": _F.GNOME,
    "kde": _F.KDE,
    "hyprland": _F.HYPRLAND,
    "sway": _F.WLROOTS,
    "river": _F.WLROOTS,
    "wayfire": _F.WLROOTS,
    "labwc": _F.WLROOTS,
    # Known desktops without a rule bundle. Listing them stops "Budgie:GNOME" from being
    # treated as GNOME: Budgie has its own compositor, so GNOME's backend does not apply.
    "budgie": _F.OTHER,
    "cinnamon": _F.OTHER,
    "x-cinnamon": _F.OTHER,
    "cosmic": _F.OTHER,
    "deepin": _F.OTHER,
    "enlightenment": _F.OTHER,
    "gnome-flashback": _F.OTHER,
    "lxde": _F.OTHER,
    "lxqt": _F.OTHER,
    "mate": _F.OTHER,
    "niri": _F.OTHER,
    "pantheon": _F.OTHER,
    "phosh": _F.OTHER,
    "unity": _F.OTHER,
    "xfce": _F.OTHER,
}
"""``XDG_CURRENT_DESKTOP`` names (lower-case). Vendor prefixes such as ``ubuntu``,
``pop`` or ``zorin`` are deliberately absent, so the next entry decides."""

SESSION_FAMILIES: dict[str, DesktopFamily] = {
    "gnome-wayland": _F.GNOME,
    "gnome-xorg": _F.GNOME,
    "gnome-classic-wayland": _F.GNOME,
    "gnome-classic-xorg": _F.GNOME,
    "ubuntu": _F.GNOME,
    "ubuntu-wayland": _F.GNOME,
    "ubuntu-xorg": _F.GNOME,
    "plasma": _F.KDE,
    "plasmawayland": _F.KDE,
    "plasmax11": _F.KDE,
    "hyprland-uwsm": _F.HYPRLAND,
}
"""Session file names that differ from the desktop name; the others are looked up in
:data:`DESKTOP_FAMILIES`. ``ubuntu`` is the name of Ubuntu's GNOME session."""


@dataclass(frozen=True, slots=True)
class DesktopIdentity:
    """Which desktop this is, and how that was decided.

    ``name`` is the recognised entry and ``source`` the variable it came from; both are
    ``None`` when nothing was recognised. ``portal_names`` and ``ignored`` are what the
    portal makes of ``XDG_CURRENT_DESKTOP``, whatever the source of ``name``.
    """

    family: DesktopFamily = DesktopFamily.UNKNOWN
    name: str | None = None
    source: str | None = None
    portal_names: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()


def identify_desktop(env: SessionEnvironment) -> DesktopIdentity:
    """Name the desktop from the first variable that holds a name this module knows."""
    portal = parse_desktop_list(env.current_desktop)
    for name in portal.names:
        if name in DESKTOP_FAMILIES:
            return DesktopIdentity(
                DESKTOP_FAMILIES[name], name, "XDG_CURRENT_DESKTOP", portal.names, portal.ignored
            )
    for variable, value in (
        ("XDG_SESSION_DESKTOP", env.session_desktop),
        ("DESKTOP_SESSION", env.desktop_session),
    ):
        session = session_name(value)
        if session is None:
            continue
        family = SESSION_FAMILIES.get(session) or DESKTOP_FAMILIES.get(session)
        if family is not None:
            return DesktopIdentity(family, session, variable, portal.names, portal.ignored)
    return DesktopIdentity(portal_names=portal.names, ignored=portal.ignored)


def session_name(value: str | None) -> str | None:
    """``plasma`` from ``plasma``, ``Plasma`` or ``/usr/share/wayland-sessions/plasma.desktop``.

    Some display managers put the path of the session file into ``DESKTOP_SESSION``.
    """
    if value is None:
        return None
    name = value.rstrip("/").rsplit("/", 1)[-1].removesuffix(".desktop").strip()
    return ascii_lower(name) or None
