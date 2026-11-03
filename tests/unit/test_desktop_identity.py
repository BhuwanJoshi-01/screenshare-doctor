"""Naming the desktop family (WLD-001)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.environment import read_session_environment
from screenshare_doctor.desktops import (
    DesktopFamily,
    DesktopIdentity,
    identify_desktop,
    session_name,
)
from screenshare_doctor.models import SessionEnvironment
from tests.fakes import read_env_fixture


@pytest.mark.parametrize(
    ("fixture", "family", "name"),
    [
        ("gnome-wayland-ubuntu", DesktopFamily.GNOME, "gnome"),
        ("kde-plasma-wayland", DesktopFamily.KDE, "kde"),
        ("hyprland", DesktopFamily.HYPRLAND, "hyprland"),
        ("gnome-x11", DesktopFamily.GNOME, "gnome"),
    ],
)
def test_fixture_desktops(fixture: str, family: DesktopFamily, name: str) -> None:
    identity = identify_desktop(read_session_environment(read_env_fixture(fixture)))
    assert (identity.family, identity.name, identity.source) == (
        family,
        name,
        "XDG_CURRENT_DESKTOP",
    )


def test_real_ubuntu_session_keeps_both_portal_names() -> None:
    identity = identify_desktop(read_session_environment(read_env_fixture("gnome-wayland-ubuntu")))
    assert identity.portal_names == ("ubuntu", "gnome")


@pytest.mark.parametrize("fixture", ["ssh-shell", "linux-console"])
def test_text_sessions_have_no_desktop(fixture: str) -> None:
    identity = identify_desktop(read_session_environment(read_env_fixture(fixture)))
    assert identity == DesktopIdentity()


@pytest.mark.parametrize(
    ("current_desktop", "family", "name"),
    [
        ("pop:GNOME", DesktopFamily.GNOME, "gnome"),
        ("zorin:GNOME", DesktopFamily.GNOME, "gnome"),
        ("GNOME-Classic:GNOME", DesktopFamily.GNOME, "gnome-classic"),
        ("Budgie:GNOME", DesktopFamily.OTHER, "budgie"),
        ("GNOME-Flashback:GNOME", DesktopFamily.OTHER, "gnome-flashback"),
        ("X-Cinnamon", DesktopFamily.OTHER, "x-cinnamon"),
        ("sway", DesktopFamily.WLROOTS, "sway"),
        ("COSMIC", DesktopFamily.OTHER, "cosmic"),
    ],
)
def test_first_known_entry_decides(current_desktop: str, family: DesktopFamily, name: str) -> None:
    identity = identify_desktop(SessionEnvironment(current_desktop=current_desktop))
    assert (identity.family, identity.name) == (family, name)


def test_unknown_names_are_not_guessed() -> None:
    identity = identify_desktop(SessionEnvironment(current_desktop="MyDesktop"))
    assert identity.family is DesktopFamily.UNKNOWN
    assert identity.name is None
    assert identity.source is None
    assert identity.portal_names == ("mydesktop",)


@pytest.mark.parametrize(
    ("session_desktop", "desktop_session", "family", "source"),
    [
        ("plasma", None, DesktopFamily.KDE, "XDG_SESSION_DESKTOP"),
        ("KDE", None, DesktopFamily.KDE, "XDG_SESSION_DESKTOP"),
        ("ubuntu", "ubuntu", DesktopFamily.GNOME, "XDG_SESSION_DESKTOP"),
        (None, "/usr/share/wayland-sessions/plasma.desktop", DesktopFamily.KDE, "DESKTOP_SESSION"),
        (None, "hyprland-uwsm", DesktopFamily.HYPRLAND, "DESKTOP_SESSION"),
        ("unknown-thing", "gnome-xorg", DesktopFamily.GNOME, "DESKTOP_SESSION"),
    ],
)
def test_session_name_is_the_fallback(
    session_desktop: str | None, desktop_session: str | None, family: DesktopFamily, source: str
) -> None:
    identity = identify_desktop(
        SessionEnvironment(session_desktop=session_desktop, desktop_session=desktop_session)
    )
    assert (identity.family, identity.source) == (family, source)
    assert identity.portal_names == ()


def test_unknown_current_desktop_still_allows_the_session_fallback() -> None:
    identity = identify_desktop(
        SessionEnvironment(current_desktop="MyDesktop", session_desktop="plasma")
    )
    assert (identity.family, identity.source) == (DesktopFamily.KDE, "XDG_SESSION_DESKTOP")
    assert identity.portal_names == ("mydesktop",)


def test_ignored_entries_are_carried_along() -> None:
    identity = identify_desktop(SessionEnvironment(current_desktop="ubuntu: GNOME"))
    assert identity.family is DesktopFamily.UNKNOWN
    assert identity.ignored == (" GNOME",)


@pytest.mark.parametrize(
    ("value", "name"),
    [
        ("plasma", "plasma"),
        ("Plasma", "plasma"),
        ("/usr/share/xsessions/gnome-xorg.desktop", "gnome-xorg"),
        ("/usr/share/wayland-sessions/", "wayland-sessions"),
        ("", None),
        ("/", None),
        (None, None),
    ],
)
def test_session_name(value: str | None, name: str | None) -> None:
    assert session_name(value) == name


_optional_text = st.none() | st.text(max_size=40)


@given(_optional_text, _optional_text, _optional_text)
def test_identify_never_raises(
    current: str | None, session_desktop: str | None, desktop_session: str | None
) -> None:
    identity = identify_desktop(
        SessionEnvironment(
            current_desktop=current,
            session_desktop=session_desktop,
            desktop_session=desktop_session,
        )
    )
    assert (identity.name is None) == (identity.family is DesktopFamily.UNKNOWN)
