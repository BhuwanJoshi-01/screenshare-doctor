"""Allowlisted session variables of the tool's own process.

The portal frontend picks its configuration from ``XDG_CURRENT_DESKTOP`` and apps decide
between Wayland and X11 from ``WAYLAND_DISPLAY`` and ``DISPLAY``, so these values explain
many screen-sharing failures. Nothing outside the allowlist is read, and the environment
is never listed: the rest of it can hold tokens and passwords.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from screenshare_doctor.models import SessionEnvironment

ALLOWLIST: tuple[str, ...] = (
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_DESKTOP",
    "DESKTOP_SESSION",
    "WAYLAND_DISPLAY",
    "DISPLAY",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_ID",
    "DBUS_SESSION_BUS_ADDRESS",
)

SSH_VARIABLES: tuple[str, ...] = ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")
"""Only whether one of these is set is kept; their values name the remote machine."""


def read_session_environment(environ: Mapping[str, str] = os.environ) -> SessionEnvironment:
    """The session variables as found; empty or blank values count as unset."""

    def value(name: str) -> str | None:
        raw = environ.get(name)
        return raw if raw is not None and raw.strip() else None

    bus = value("DBUS_SESSION_BUS_ADDRESS")
    return SessionEnvironment(
        session_type=value("XDG_SESSION_TYPE"),
        current_desktop=value("XDG_CURRENT_DESKTOP"),
        session_desktop=value("XDG_SESSION_DESKTOP"),
        desktop_session=value("DESKTOP_SESSION"),
        wayland_display=value("WAYLAND_DISPLAY"),
        display=value("DISPLAY"),
        runtime_dir=value("XDG_RUNTIME_DIR"),
        session_id=value("XDG_SESSION_ID"),
        dbus_session_bus_address=_without_guid(bus) if bus is not None else None,
        ssh=any(value(name) is not None for name in SSH_VARIABLES),
    )


def _without_guid(address: str) -> str:
    """Drop the ``guid=`` key from every address in a D-Bus address list.

    The guid identifies one bus instance and is useless in a shared report. The format
    is ``transport:key=value,key=value`` with ``;`` between alternatives.
    """
    kept: list[str] = []
    for alternative in address.split(";"):
        transport, colon, params = alternative.partition(":")
        if not colon:
            kept.append(alternative)
            continue
        pairs = [pair for pair in params.split(",") if pair and not pair.startswith("guid=")]
        kept.append(f"{transport}:{','.join(pairs)}")
    return ";".join(kept)
