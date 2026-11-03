"""``.portal`` descriptors and ``portals.conf`` files, judged as the portal frontend would.

The checks mirror ``register_portal()`` and ``load_portal_configuration_for_dir()`` in
xdg-desktop-portal (``desktop-portal/xdp-portal-config.c``): a descriptor needs a valid
``DBusName`` and an ``Interfaces`` list of ``org.freedesktop.impl.portal.*`` names, and
a configuration file needs a ``[preferred]`` group. Files that fail are kept, with the
reason, because "the portal ignored your file" is often the answer.

Pure functions: the bytes are read elsewhere.
"""

from __future__ import annotations

import re

from screenshare_doctor.keyfile import KeyFileError, parse_keyfile
from screenshare_doctor.models import PortalDescriptor, PortalsConf

IMPL_PREFIX = "org.freedesktop.impl.portal."

_BUS_ELEMENT = re.compile(r"[A-Za-z_-][A-Za-z0-9_-]*", re.ASCII)
_UNIQUE_ELEMENT = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)
_INTERFACE_ELEMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)


def is_bus_name(name: str) -> bool:
    """``g_dbus_is_name``: a well-known (``a.b``) or unique (``:1.42``) bus name."""
    if not name or len(name) > 255:
        return False
    unique = name.startswith(":")
    elements = (name[1:] if unique else name).split(".")
    pattern = _UNIQUE_ELEMENT if unique else _BUS_ELEMENT
    return len(elements) >= 2 and all(pattern.fullmatch(element) for element in elements)


def is_interface_name(name: str) -> bool:
    """``g_dbus_is_interface_name``: at least two elements, no ``-``, at most 255 bytes."""
    if not name or len(name) > 255:
        return False
    elements = name.split(".")
    return len(elements) >= 2 and all(_INTERFACE_ELEMENT.fullmatch(e) for e in elements)


def source_name(file_name: str) -> str:
    """``gnome`` from ``gnome.portal``: everything before the last dot."""
    return file_name.rsplit(".", 1)[0]


def parse_descriptor(path: str, data: bytes) -> PortalDescriptor:
    """Read one ``.portal`` file; ``error`` is set when the portal would skip it."""
    source = source_name(path.rsplit("/", 1)[-1])
    try:
        keyfile = parse_keyfile(data)
        dbus_name = keyfile.get_string("portal", "DBusName")
        interfaces = keyfile.get_string_list("portal", "Interfaces")
        use_in = keyfile.get_string_list("portal", "UseIn")
    except KeyFileError as exc:
        return PortalDescriptor(source, path, error=f"unreadable: {exc}")
    if dbus_name is None:
        return PortalDescriptor(source, path, error="no DBusName in [portal]")
    if not is_bus_name(dbus_name):
        return PortalDescriptor(source, path, dbus_name, error=f"not a valid bus name: {dbus_name}")
    if interfaces is None:
        return PortalDescriptor(source, path, dbus_name, error="no Interfaces in [portal]")
    for interface in interfaces:
        if not is_interface_name(interface):
            return PortalDescriptor(
                source, path, dbus_name, error=f"not a valid interface name: {interface!r}"
            )
        if not interface.startswith(IMPL_PREFIX):
            return PortalDescriptor(
                source, path, dbus_name, error=f"not a portal backend interface: {interface}"
            )
    return PortalDescriptor(source, path, dbus_name, interfaces, use_in)


def parse_portals_conf(path: str, data: bytes) -> PortalsConf:
    """Read one portals.conf; ``usable`` is ``False`` when the portal would ignore it."""
    try:
        keyfile = parse_keyfile(data)
    except KeyFileError as exc:
        return PortalsConf(path, usable=False, error=f"unreadable: {exc}")
    if not keyfile.has_group("preferred"):
        return PortalsConf(path, usable=False, error="no [preferred] group")
    preferred: list[tuple[str, tuple[str, ...]]] = []
    for key in keyfile.keys("preferred"):
        try:
            portals = keyfile.get_string_list("preferred", key)
        except KeyFileError as exc:
            # The portal gives up on the whole file ("Invalid portals for interface").
            return PortalsConf(path, usable=False, error=f"invalid value for {key}: {exc}")
        preferred.append((key, portals or ()))
    duplicates = tuple(key for group, key in keyfile.duplicates if group == "preferred")
    return PortalsConf(path, tuple(preferred), duplicates)
