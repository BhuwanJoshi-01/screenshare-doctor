"""Where xdg-desktop-portal looks for ``portals.conf`` and ``.portal`` files.

The order follows ``load_portal_configurations()`` and ``load_installed_portals()`` in
``desktop-portal/xdp-portal-config.c``, with GLib's defaults for unset variables
(``~/.config``, ``/etc/xdg``, ``~/.local/share``, ``/usr/local/share:/usr/share``).
``SYSCONFDIR`` and ``DATADIR`` are fixed when the portal is built; every major
distribution uses ``/etc`` and ``/usr/share``.

Pure functions of the variables; nothing is read here.
"""

from __future__ import annotations

from screenshare_doctor.models import XdgDirectories

SUBDIR = "xdg-desktop-portal"
SYSCONFDIR = "/etc"
DATADIR = "/usr/share"
DEFAULT_CONFIG_DIRS = "/etc/xdg"
DEFAULT_DATA_DIRS = "/usr/local/share/:/usr/share/"


def join(*parts: str) -> str:
    """Join path parts with single slashes, as ``g_build_filename`` does."""
    pieces = [part.strip("/") for part in parts if part.strip("/")]
    return ("/" if parts and parts[0].startswith("/") else "") + "/".join(pieces)


def _split(value: str | None, default: str) -> tuple[str, ...]:
    chosen = value if value else default
    return tuple(entry for entry in chosen.split(":") if entry)


def _user_dir(value: str | None, home: str | None, fallback: str) -> str | None:
    if value:
        return value
    return join(home, fallback) if home else None


def _once(directories: list[str]) -> tuple[str, ...]:
    """Each directory at its first position. The portal stops at the first file it finds,
    so searching a directory again (``/usr/share`` from ``XDG_DATA_DIRS`` and again as
    ``DATADIR``) can never change the result."""
    return tuple(dict.fromkeys(directories))


def config_directories(dirs: XdgDirectories) -> tuple[str, ...]:
    """The directories searched for ``(DESKTOP-)portals.conf``, highest priority first."""
    if dirs.portal_dir:
        return (dirs.portal_dir,)
    found: list[str] = []
    user_config = _user_dir(dirs.config_home, dirs.home, ".config")
    if user_config:
        found.append(join(user_config, SUBDIR))
    found += [join(entry, SUBDIR) for entry in _split(dirs.config_dirs, DEFAULT_CONFIG_DIRS)]
    found.append(join(SYSCONFDIR, SUBDIR))
    user_data = _user_dir(dirs.data_home, dirs.home, ".local/share")
    if user_data:
        found.append(join(user_data, SUBDIR))
    found += [join(entry, SUBDIR) for entry in _split(dirs.data_dirs, DEFAULT_DATA_DIRS)]
    found.append(join(DATADIR, SUBDIR))
    return _once(found)


def descriptor_directories(dirs: XdgDirectories) -> tuple[str, ...]:
    """The directories searched for ``*.portal`` files; the first file of a name wins."""
    if dirs.portal_dir:
        return (dirs.portal_dir,)
    found: list[str] = []
    user_data = _user_dir(dirs.data_home, dirs.home, ".local/share")
    if user_data:
        found.append(join(user_data, SUBDIR, "portals"))
    found += [join(entry, SUBDIR, "portals") for entry in _split(dirs.data_dirs, DEFAULT_DATA_DIRS)]
    found.append(join(DATADIR, SUBDIR, "portals"))
    return _once(found)


def config_candidates(directory: str, desktops: tuple[str, ...]) -> tuple[str, ...]:
    """The files tried in one directory: ``<desktop>-portals.conf`` for each desktop in
    order, then ``portals.conf``."""
    return (
        *(join(directory, f"{desktop}-portals.conf") for desktop in desktops),
        join(directory, "portals.conf"),
    )
