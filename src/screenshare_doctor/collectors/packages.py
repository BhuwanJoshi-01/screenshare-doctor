"""Installed packages of the screen-sharing stack, read from the package manager.

Only query commands are used (``dpkg-query -W``, ``rpm -q``, ``pacman -Q``); they read
the package database and change nothing. A package counts as not installed only when
the package manager says so; output that mentions neither state leaves it unknown.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from screenshare_doctor.models import PackageInfo, PackageState

PACKAGES: tuple[str, ...] = (
    "xdg-desktop-portal",
    "xdg-desktop-portal-gnome",
    "xdg-desktop-portal-gtk",
    "xdg-desktop-portal-kde",
    "xdg-desktop-portal-wlr",
    "xdg-desktop-portal-hyprland",
    "pipewire",
    "wireplumber",
)
"""The same names on Debian, Ubuntu, Fedora, openSUSE and Arch."""

DPKG_FORMAT = "${Package}\\t${Version}\\t${db:Status-Abbrev}\\n"

# db:Status-Abbrev is three characters: wanted, current state, error flag. Current
# states: n not installed, c config files only, H half installed, U unpacked,
# F half configured, W triggers awaited, t triggers pending, i installed.
_DPKG_CURRENT = {
    "i": PackageState.INSTALLED,
    "W": PackageState.INSTALLED,
    "t": PackageState.INSTALLED,
    "n": PackageState.NOT_INSTALLED,
    "c": PackageState.NOT_INSTALLED,
    "H": PackageState.BROKEN,
    "U": PackageState.BROKEN,
    "F": PackageState.BROKEN,
}


def parse_dpkg(
    stdout: str, stderr: str, names: Sequence[str] = PACKAGES
) -> tuple[PackageInfo, ...]:
    """``dpkg-query -W -f DPKG_FORMAT names…`` output, in the order of ``names``.

    dpkg-query exits with 1 when some names are unknown to it and says so on stderr
    ("no packages found matching NAME"); the others are still printed on stdout.
    """
    found: dict[str, PackageInfo] = {}
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] not in names:
            continue
        name, version, status = parts
        current = status[1:2]
        state = _DPKG_CURRENT.get(current, PackageState.UNKNOWN)
        if status[2:3] == "R" and state is PackageState.INSTALLED:
            state = PackageState.BROKEN
        if state is PackageState.NOT_INSTALLED:
            found[name] = PackageInfo(name, state)
        else:
            found[name] = PackageInfo(name, state, version or None)
    missing = set(re.findall(r"no packages found matching (\S+)", stderr))
    return _in_order(names, found, missing)


def _in_order(
    names: Sequence[str], found: dict[str, PackageInfo], missing: set[str]
) -> tuple[PackageInfo, ...]:
    result = []
    for name in names:
        if name in found:
            result.append(found[name])
        elif name in missing:
            result.append(PackageInfo(name, PackageState.NOT_INSTALLED))
        else:
            result.append(PackageInfo(name, PackageState.UNKNOWN))
    return tuple(result)
