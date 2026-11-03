"""Parsing loginctl show-* output (WLD-001)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.logind import parse_properties, parse_session
from screenshare_doctor.models import LogindSession
from tests.fakes import read_fixture


def test_real_gnome_wayland_session() -> None:
    session = parse_session(read_fixture("loginctl", "show-session-gnome-wayland.txt"))
    assert session == LogindSession(
        id="63",
        session_type="wayland",
        session_class="user",
        desktop=None,
        remote=False,
        active=True,
        state="active",
        seat="seat0",
    )


def test_real_user_manager_session_has_no_seat() -> None:
    session = parse_session(read_fixture("loginctl", "show-session-user-manager.txt"))
    assert session is not None
    assert (session.session_type, session.session_class, session.seat) == (
        "unspecified",
        "manager",
        None,
    )


def test_ssh_session_is_remote() -> None:
    session = parse_session(read_fixture("loginctl", "show-session-ssh.txt"))
    assert session is not None
    assert session.remote is True
    assert session.session_type == "tty"
    assert session.active is False


def test_desktop_is_read_when_set() -> None:
    session = parse_session(read_fixture("loginctl", "show-session-kde-wayland.txt"))
    assert session is not None
    assert session.desktop == "KDE"


def test_real_show_user_display() -> None:
    assert parse_properties(read_fixture("loginctl", "show-user-display-gnome.txt")) == {
        "Display": "63"
    }


def test_values_may_contain_equals_signs() -> None:
    assert parse_properties("Desktop=a=b\n") == {"Desktop": "a=b"}


def test_noise_lines_are_skipped() -> None:
    text = "Failed to parse something\n\n=orphan\nType=x11\nnot a property line\n"
    assert parse_properties(text) == {"Type": "x11"}


def test_output_without_an_id_is_no_session() -> None:
    assert parse_session("Type=wayland\n") is None
    assert parse_session("") is None


def test_unknown_booleans_stay_unknown() -> None:
    session = parse_session("Id=4\nRemote=maybe\nActive=\n")
    assert session is not None
    assert session.remote is None
    assert session.active is None


@given(st.text())
def test_parsing_never_raises(text: str) -> None:
    parse_session(text)
