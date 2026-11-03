"""Descriptors and portals.conf as the portal frontend judges them (WLD-005)."""

from __future__ import annotations

import pytest

from screenshare_doctor.portal_files import (
    is_bus_name,
    is_interface_name,
    parse_descriptor,
    parse_portals_conf,
    source_name,
)
from tests.fakes import FIXTURES

SHARE = "/usr/share/xdg-desktop-portal"


def _fixture(name: str) -> bytes:
    return (FIXTURES / "portals" / name).read_bytes()


def test_real_gnome_descriptor() -> None:
    descriptor = parse_descriptor(f"{SHARE}/portals/gnome.portal", _fixture("gnome.portal"))
    assert descriptor.error is None
    assert descriptor.source == "gnome"
    assert descriptor.dbus_name == "org.freedesktop.impl.portal.desktop.gnome"
    assert "org.freedesktop.impl.portal.ScreenCast" in descriptor.interfaces
    assert descriptor.use_in == ("gnome",)


def test_real_gtk_descriptor_has_no_screencast() -> None:
    descriptor = parse_descriptor(f"{SHARE}/portals/gtk.portal", _fixture("gtk.portal"))
    assert descriptor.error is None
    assert "org.freedesktop.impl.portal.ScreenCast" not in descriptor.interfaces


def test_real_gnome_keyring_descriptor_uses_another_bus_name() -> None:
    descriptor = parse_descriptor(
        f"{SHARE}/portals/gnome-keyring.portal", _fixture("gnome-keyring.portal")
    )
    assert descriptor.error is None
    assert descriptor.source == "gnome-keyring"
    assert descriptor.dbus_name == "org.freedesktop.secrets"


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (b"[portal]\nInterfaces=org.freedesktop.impl.portal.ScreenCast\n", "no DBusName"),
        (b"[portal]\nDBusName=nodots\nInterfaces=org.freedesktop.impl.portal.A\n", "bus name"),
        (b"[portal]\nDBusName=a.b\n", "no Interfaces"),
        (b"[portal]\nDBusName=a.b\nInterfaces=org.freedesktop.portal.ScreenCast\n", "backend"),
        (b"[portal]\nDBusName=a.b\nInterfaces=org.freedesktop.impl.portal.Screen-Cast\n", "valid"),
        (b"DBusName=a.b\n", "unreadable"),
        (b"[other]\nDBusName=a.b\n", "no DBusName"),
    ],
)
def test_descriptors_the_portal_skips(data: bytes, error: str) -> None:
    descriptor = parse_descriptor("/x/broken.portal", data)
    assert descriptor.error is not None
    assert error in descriptor.error
    assert descriptor.interfaces == ()


def test_real_gnome_portals_conf() -> None:
    conf = parse_portals_conf(f"{SHARE}/gnome-portals.conf", _fixture("gnome-portals.conf"))
    assert conf.usable
    assert conf.preferred == (
        ("default", ("gnome", "gtk")),
        ("org.freedesktop.impl.portal.Secret", ("gnome-keyring",)),
    )


def test_conf_without_preferred_group_is_ignored() -> None:
    conf = parse_portals_conf("/x/portals.conf", b"[other]\ndefault=gnome\n")
    assert not conf.usable
    assert conf.error == "no [preferred] group"


def test_empty_preferred_group_is_still_a_config() -> None:
    # load_portal_configuration_for_dir() returns a config for an empty group too.
    conf = parse_portals_conf("/x/portals.conf", b"[preferred]\n")
    assert conf.usable
    assert conf.preferred == ()


def test_unreadable_conf() -> None:
    conf = parse_portals_conf("/x/portals.conf", b"[preferred]\ndefault gnome\n")
    assert not conf.usable
    assert conf.error is not None
    assert conf.error.startswith("unreadable")


def test_invalid_list_value_makes_the_whole_file_unusable() -> None:
    conf = parse_portals_conf("/x/portals.conf", b"[preferred]\ndefault=gn\\qome\n")
    assert not conf.usable


def test_duplicate_default_keeps_the_last_value() -> None:
    conf = parse_portals_conf("/x/portals.conf", b"[preferred]\ndefault=gnome\ndefault=kde;gtk\n")
    assert conf.preferred == (("default", ("kde", "gtk")),)
    assert conf.duplicates == ("default",)


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("org.freedesktop.impl.portal.desktop.gnome", True),
        ("org.freedesktop.secrets", True),
        ("org.kde.kwin-wayland.x", True),
        (":1.42", True),
        ("nodots", False),
        ("a..b", False),
        ("1a.b", False),
        ("", False),
        ("a." + "b" * 300, False),
    ],
)
def test_bus_names(name: str, valid: bool) -> None:
    assert is_bus_name(name) is valid


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("org.freedesktop.impl.portal.ScreenCast", True),
        ("org.freedesktop.impl.portal.Screen-Cast", False),
        ("ScreenCast", False),
        ("org.9x", False),
    ],
)
def test_interface_names(name: str, valid: bool) -> None:
    assert is_interface_name(name) is valid


def test_source_name() -> None:
    assert source_name("gnome.portal") == "gnome"
    assert source_name("gnome-keyring.portal") == "gnome-keyring"
    assert source_name("odd.name.portal") == "odd.name"
