"""Allowlisted session variables of the tool's own process.

The portal frontend picks its configuration from ``XDG_CURRENT_DESKTOP`` and apps decide
between Wayland and X11 from ``WAYLAND_DISPLAY`` and ``DISPLAY``, so these values explain
many screen-sharing failures. Nothing outside the allowlist is read, and the environment
is never listed: the rest of it can hold tokens and passwords.
"""

from __future__ import annotations

import os
import re
import stat as stat_module
from collections.abc import Callable, Mapping

from screenshare_doctor.models import PathState, SessionEnvironment, SessionPaths, XdgDirectories

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


XDG_DIRECTORY_VARIABLES: tuple[str, ...] = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_CONFIG_DIRS",
    "XDG_DATA_HOME",
    "XDG_DATA_DIRS",
    "XDG_DESKTOP_PORTAL_DIR",
)
"""The second, separate allowlist: the variables that decide where portals look for files."""


def read_xdg_directories(environ: Mapping[str, str] = os.environ) -> XdgDirectories:
    """The directory variables as found; empty values count as unset (as in GLib)."""

    def value(name: str) -> str | None:
        raw = environ.get(name)
        return raw if raw else None

    return XdgDirectories(
        home=value("HOME"),
        config_home=value("XDG_CONFIG_HOME"),
        config_dirs=value("XDG_CONFIG_DIRS"),
        data_home=value("XDG_DATA_HOME"),
        data_dirs=value("XDG_DATA_DIRS"),
        portal_dir=value("XDG_DESKTOP_PORTAL_DIR"),
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


_X11_LOCAL_DISPLAY = re.compile(r"(?:unix)?:(\d+)(?:\.\d+)?")
"""``:0``, ``:1.0`` or ``unix:0``: a display served on a local socket. ``host:10.0`` is TCP."""

X11_SOCKET_DIR = "/tmp/.X11-unix"  # noqa: S108 - fixed by the X protocol, only stat()ed


def check_session_paths(
    env: SessionEnvironment, *, stat: Callable[[str], os.stat_result] = os.stat
) -> SessionPaths:
    """Look at the runtime directory and the display sockets the variables point to.

    Only ``stat`` is used: nothing is opened or connected to. A relative
    ``WAYLAND_DISPLAY`` lives in ``XDG_RUNTIME_DIR``; an absolute one is used as is, as
    libwayland does. Without the variables the paths are not guessed.
    """
    runtime = env.runtime_dir
    wayland_path: str | None = None
    if env.wayland_display is not None:
        if env.wayland_display.startswith("/"):
            wayland_path = env.wayland_display
        elif runtime is not None:
            wayland_path = f"{runtime.rstrip('/')}/{env.wayland_display}"
    x11_path: str | None = None
    if env.display is not None and (match := _X11_LOCAL_DISPLAY.fullmatch(env.display)):
        x11_path = f"{X11_SOCKET_DIR}/X{match.group(1)}"
    return SessionPaths(
        runtime_dir=_state(runtime, stat, want=stat_module.S_ISDIR),
        wayland_socket=_state(wayland_path, stat, want=stat_module.S_ISSOCK),
        wayland_socket_path=wayland_path,
        x11_socket=_state(x11_path, stat, want=stat_module.S_ISSOCK),
        x11_socket_path=x11_path,
    )


def _state(
    path: str | None, stat: Callable[[str], os.stat_result], *, want: Callable[[int], bool]
) -> PathState:
    if path is None:
        return PathState.NOT_CHECKED
    try:
        mode = stat(path).st_mode
    except FileNotFoundError:
        return PathState.MISSING
    except OSError:  # permission denied, a file where a directory should be, too long…
        return PathState.UNREADABLE
    if not want(mode):
        return PathState.OTHER
    return PathState.DIRECTORY if stat_module.S_ISDIR(mode) else PathState.SOCKET
