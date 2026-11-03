"""User services of the screen-sharing stack, read from the user's systemd manager.

``systemctl --user show`` and ``show-environment`` only read state; they never start,
stop or reload a unit, so a portal that is not running stays that way.
"""

from __future__ import annotations

from collections.abc import Sequence

from screenshare_doctor.collectors.environment import (
    read_session_environment,
    read_xdg_directories,
)
from screenshare_doctor.models import (
    FailureKind,
    ProbeFailure,
    ServiceFacts,
    SessionEnvironment,
    UserService,
    XdgDirectories,
)
from screenshare_doctor.runner import CommandRunner, probe_failure

UNITS: tuple[str, ...] = (
    "xdg-desktop-portal.service",
    "xdg-desktop-portal-gnome.service",
    "xdg-desktop-portal-gtk.service",
    "plasma-xdg-desktop-portal-kde.service",
    "xdg-desktop-portal-wlr.service",
    "xdg-desktop-portal-hyprland.service",
    "pipewire.socket",
    "pipewire.service",
    "wireplumber.service",
)
"""Plasma 6 names its backend unit ``plasma-xdg-desktop-portal-kde.service``."""

UNIT_PROPERTIES: tuple[str, ...] = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState")


def parse_units(text: str, units: Sequence[str] = UNITS) -> tuple[UserService, ...]:
    """``systemctl --user show -p … units…`` output: one block per unit, blank-line separated.

    Blocks are matched to the requested names by their ``Id``, which equals the name for
    the units listed here; a requested unit without a block gets no states.
    """
    blocks: dict[str, dict[str, str]] = {}
    for block in text.split("\n\n"):
        properties: dict[str, str] = {}
        for line in block.splitlines():
            key, equals, raw = line.partition("=")
            if equals and key in UNIT_PROPERTIES:
                properties[key] = raw.strip()
        unit_id = properties.get("Id")
        if unit_id and unit_id not in blocks:
            blocks[unit_id] = properties

    services = []
    for unit in units:
        found = blocks.get(unit, {})
        services.append(
            UserService(
                unit,
                load_state=found.get("LoadState") or None,
                active_state=found.get("ActiveState") or None,
                sub_state=found.get("SubState") or None,
                unit_file_state=found.get("UnitFileState") or None,
            )
        )
    return tuple(services)


def parse_activation_environment(text: str) -> tuple[SessionEnvironment, XdgDirectories]:
    """The allowlisted variables from ``systemctl --user show-environment``.

    The output is the user manager's whole environment and can hold secrets; it is
    turned into a mapping only to look the allowlisted names up (session variables and
    XDG directories), and nothing else of it is kept.
    """
    variables: dict[str, str] = {}
    for line in text.splitlines():
        name, equals, value = line.partition("=")
        if equals and name:
            variables[name] = value
    return read_session_environment(variables), read_xdg_directories(variables)


SYSTEMCTL_TIMEOUT = 5.0


def collect_services(
    runner: CommandRunner, *, units: Sequence[str] = UNITS
) -> tuple[ServiceFacts, tuple[ProbeFailure, ...]]:
    """Unit states, then the manager's environment; stops at the first failure.

    Both commands talk to the same user manager, so when the first cannot reach it (no
    systemd, no user session bus) the second would only repeat the same error.
    """
    argv = ["systemctl", "--user", "--no-pager", "show"]
    for name in UNIT_PROPERTIES:
        argv += ["-p", name]
    result = runner.run([*argv, *units], timeout=SYSTEMCTL_TIMEOUT)
    failure = probe_failure("systemctl --user show", result)
    if failure is not None:
        return ServiceFacts(), (failure,)
    services = parse_units(result.stdout, units)
    if all(service.load_state is None for service in services):
        return ServiceFacts(), (
            ProbeFailure(
                "systemctl --user show", FailureKind.MALFORMED_OUTPUT, "no unit was described"
            ),
        )

    result = runner.run(
        ["systemctl", "--user", "--no-pager", "show-environment"], timeout=SYSTEMCTL_TIMEOUT
    )
    failure = probe_failure("systemctl --user show-environment", result)
    if failure is not None:
        return ServiceFacts(services=services), (failure,)
    environment, directories = parse_activation_environment(result.stdout)
    return ServiceFacts(services, environment, directories), ()
