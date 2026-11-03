"""Introspection and ScreenCast property replies (WLD-004)."""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.dbus import (
    IMPL_SCREENCAST,
    SCREENCAST,
    BusctlOutputError,
    parse_integer_property,
    parse_introspection,
    parse_screencast_properties,
)
from screenshare_doctor.models import ScreenCastProperties
from tests.fakes import read_fixture


def test_real_frontend_exposes_screencast() -> None:
    interfaces = parse_introspection(
        read_fixture("busctl", "introspect-frontend-ubuntu-gnome.json")
    )
    assert SCREENCAST in interfaces
    assert "org.freedesktop.portal.RemoteDesktop" in interfaces
    assert "org.freedesktop.DBus.Properties" not in interfaces
    assert list(interfaces) == sorted(set(interfaces))


def test_real_gnome_backend_implements_screencast() -> None:
    interfaces = parse_introspection(read_fixture("busctl", "introspect-gnome-backend.json"))
    assert IMPL_SCREENCAST in interfaces


def test_real_gtk_backend_does_not() -> None:
    interfaces = parse_introspection(read_fixture("busctl", "introspect-gtk-backend.json"))
    assert IMPL_SCREENCAST not in interfaces
    assert "org.freedesktop.impl.portal.FileChooser" in interfaces


def test_real_screencast_properties() -> None:
    for fixture in ("screencast-props-frontend.json", "screencast-props-gnome-backend.json"):
        assert parse_screencast_properties(read_fixture("busctl", fixture)) == (
            ScreenCastProperties(version=5, source_types=7, cursor_modes=7)
        )


def test_real_mutter_version() -> None:
    assert parse_integer_property(read_fixture("busctl", "mutter-screencast-version.json")) == 4


def test_entities_are_not_expanded() -> None:
    xml = (
        '<!DOCTYPE n [<!ENTITY a "org.freedesktop.portal.Evil">]>'
        '<node><interface name="&a;"/></node>'
    )
    assert parse_introspection(json.dumps({"type": "s", "data": [xml]})) == ()


@pytest.mark.parametrize(
    "text",
    [
        '{"type":"u","data":5}\n{"type":"u","data":7}\n',
        '{"type":"u","data":5}\n{"type":"s","data":"7"}\n{"type":"u","data":7}\n',
        '{"type":"u","data":5}\n{"type":"b","data":true}\n{"type":"u","data":7}\n',
        '{"type":"i","data":-1}\n{"type":"u","data":7}\n{"type":"u","data":7}\n',
    ],
)
def test_bad_property_replies(text: str) -> None:
    with pytest.raises(BusctlOutputError):
        parse_screencast_properties(text)


@pytest.mark.parametrize("text", ['{"type":"as","data":[["x"]]}', '{"type":"s","data":[1]}'])
def test_bad_introspection_replies(text: str) -> None:
    with pytest.raises(BusctlOutputError):
        parse_introspection(text)


@given(st.text())
def test_introspection_never_returns_non_portal_names(xml: str) -> None:
    for name in parse_introspection(json.dumps({"type": "s", "data": [xml]})):
        assert name.startswith("org.freedesktop.")
