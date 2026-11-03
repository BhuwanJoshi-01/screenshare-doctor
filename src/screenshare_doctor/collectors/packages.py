"""Installed packages of the screen-sharing stack, read from the package manager.

Only query commands are used (``dpkg-query -W``, ``rpm -q``, ``pacman -Q``); they read
the package database and change nothing. A package counts as not installed only when
the package manager says so; output that mentions neither state leaves it unknown.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path

from screenshare_doctor.models import (
    FailureKind,
    PackageFacts,
    PackageInfo,
    PackageState,
    ProbeFailure,
)
from screenshare_doctor.runner import CommandResult, CommandRunner, Outcome, probe_failure

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


RPM_FORMAT = "%{NAME}\\t%{VERSION}-%{RELEASE}\\n"

_RPM_MISSING = re.compile(r"package (\S+) is not installed")
_PACMAN_MISSING = re.compile(r"error: package '([^']+)' was not found")


def parse_rpm(stdout: str, names: Sequence[str] = PACKAGES) -> tuple[PackageInfo, ...]:
    """``rpm -q --queryformat RPM_FORMAT names…`` output, in the order of ``names``.

    rpm reports missing packages on stdout ("package NAME is not installed"). A package
    installed for two architectures prints two lines; the first one is kept.
    """
    found: dict[str, PackageInfo] = {}
    missing: set[str] = set()
    for line in stdout.splitlines():
        if match := _RPM_MISSING.fullmatch(line.strip()):
            missing.add(match.group(1))
            continue
        name, tab, version = line.partition("\t")
        if tab and name in names and name not in found:
            found[name] = PackageInfo(name, PackageState.INSTALLED, version.strip() or None)
    return _in_order(names, found, missing)


def parse_pacman(
    stdout: str, stderr: str, names: Sequence[str] = PACKAGES
) -> tuple[PackageInfo, ...]:
    """``pacman -Q names…`` output (``name version`` lines), in the order of ``names``.

    pacman reports missing packages on stderr ("error: package 'NAME' was not found").
    """
    found: dict[str, PackageInfo] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in names:
            found[parts[0]] = PackageInfo(parts[0], PackageState.INSTALLED, parts[1])
    missing = set(_PACMAN_MISSING.findall(stderr))
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


PACKAGE_TIMEOUT = 15.0
"""Seconds; a cold rpm database can take a few."""

MANAGERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("dpkg", "dpkg-query", ("/var/lib/dpkg/status",)),
    ("rpm", "rpm", ("/usr/lib/sysimage/rpm", "/var/lib/rpm")),
    ("pacman", "pacman", ("/var/lib/pacman/local",)),
)
"""Name, query program and database paths. A manager counts only when its database
exists too: an rpm binary on a Debian system (installed for alien) knows nothing."""

PROGRAM_DIRS: tuple[str, ...] = ("/usr/libexec", "/usr/lib", "/usr/local/libexec")
"""Where distributions put the portal programs (Debian and Fedora: libexec; Arch: lib)."""


def _exists(path: str) -> bool:
    return Path(path).exists()


def collect_packages(
    runner: CommandRunner,
    *,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = _exists,
    names: Sequence[str] = PACKAGES,
) -> tuple[PackageFacts, tuple[ProbeFailure, ...]]:
    """Ask the system's package manager; without one, look for the installed programs."""
    for manager, program, databases in MANAGERS:
        if which(program) is None or not any(exists(db) for db in databases):
            continue
        result = runner.run(_query(manager, names), timeout=PACKAGE_TIMEOUT)
        packages = _parse(manager, result, names)
        if packages is not None:
            return PackageFacts(manager, packages), ()
        failure = probe_failure(f"{program} query", result) or ProbeFailure(
            f"{program} query", FailureKind.MALFORMED_OUTPUT, "no package was listed"
        )
        return _from_files(names, which, exists), (failure,)
    return _from_files(names, which, exists), ()


def _query(manager: str, names: Sequence[str]) -> list[str]:
    if manager == "dpkg":
        return ["dpkg-query", "-W", "-f", DPKG_FORMAT, *names]
    if manager == "rpm":
        return ["rpm", "-q", "--queryformat", RPM_FORMAT, *names]
    return ["pacman", "-Q", *names]


def _parse(
    manager: str, result: CommandResult, names: Sequence[str]
) -> tuple[PackageInfo, ...] | None:
    """The parsed answer, or ``None`` when the command gave none.

    All three exit non-zero when some names are not installed, so a non-zero exit is
    accepted as long as the output answers for at least one name.
    """
    if result.outcome not in {Outcome.OK, Outcome.NONZERO}:
        return None
    if manager == "dpkg":
        packages = parse_dpkg(result.stdout, result.stderr, names)
    elif manager == "rpm":
        packages = parse_rpm(result.stdout, names)
    else:
        packages = parse_pacman(result.stdout, result.stderr, names)
    if all(p.state is PackageState.UNKNOWN for p in packages):
        return None
    return packages


def _from_files(
    names: Sequence[str], which: Callable[[str], str | None], exists: Callable[[str], bool]
) -> PackageFacts:
    """INSTALLED when the package's program is found, otherwise UNKNOWN (never "not
    installed": the program may live somewhere this list does not know)."""
    packages = []
    for name in names:
        if name.startswith("xdg-desktop-portal"):
            found = any(exists(f"{directory}/{name}") for directory in PROGRAM_DIRS)
        else:
            found = which(name) is not None
        packages.append(
            PackageInfo(name, PackageState.INSTALLED if found else PackageState.UNKNOWN)
        )
    return PackageFacts("files", tuple(packages))
