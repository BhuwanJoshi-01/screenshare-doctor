"""Telling Wayland, X11, SSH and no session apart (WLD-001)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.environment import read_session_environment
from screenshare_doctor.models import (
    LogindFacts,
    LogindSession,
    PathState,
    SessionEnvironment,
    SessionPaths,
)
from screenshare_doctor.session import Location, SessionAssessment, SessionKind, assess_session
from tests.fakes import read_env_fixture

SOCKETS = SessionPaths(
    runtime_dir=PathState.DIRECTORY,
    wayland_socket=PathState.SOCKET,
    x11_socket=PathState.SOCKET,
)
GNOME = LogindSession(id="63", session_type="wayland", session_class="user", seat="seat0")
X11_DESKTOP = LogindSession(id="4", session_type="x11", session_class="user", seat="seat0")
SSH = LogindSession(id="7", session_type="tty", session_class="user", remote=True)


NO_LOGIND = LogindFacts()


def _assess(
    fixture: str, logind: LogindFacts = NO_LOGIND, paths: SessionPaths = SOCKETS
) -> SessionAssessment:
    return assess_session(read_session_environment(read_env_fixture(fixture)), paths, logind)


def test_real_gnome_terminal_without_session_id() -> None:
    result = _assess("gnome-wayland-ubuntu", LogindFacts(display=GNOME, display_known=True))
    assert (result.kind, result.location, result.source) == (
        SessionKind.WAYLAND,
        Location.DESKTOP,
        "environment",
    )
    assert result.notes == ()


@pytest.mark.parametrize(
    ("fixture", "kind"),
    [
        ("kde-plasma-wayland", SessionKind.WAYLAND),
        ("hyprland", SessionKind.WAYLAND),
        ("gnome-x11", SessionKind.X11),
    ],
)
def test_desktop_fixtures(fixture: str, kind: SessionKind) -> None:
    result = _assess(fixture)
    assert (result.kind, result.location, result.source) == (kind, Location.DESKTOP, "environment")


def test_ssh_login_describes_the_desktop_through_logind() -> None:
    result = _assess("ssh-shell", LogindFacts(own=SSH, display=GNOME, display_known=True))
    assert (result.kind, result.location, result.source) == (
        SessionKind.WAYLAND,
        Location.SSH,
        "logind",
    )


def test_ssh_without_a_desktop() -> None:
    result = _assess("ssh-shell", LogindFacts(own=SSH, display_known=True))
    assert (result.kind, result.location) == (SessionKind.NONE, Location.SSH)


def test_ssh_flag_alone_is_enough() -> None:
    result = assess_session(SessionEnvironment(ssh=True), SessionPaths(), LogindFacts())
    assert (result.kind, result.location, result.source) == (
        SessionKind.UNKNOWN,
        Location.SSH,
        None,
    )


def test_remote_logind_session_without_ssh_variables() -> None:
    # sudo -i or su can drop the SSH variables; logind still knows the login is remote.
    result = assess_session(SessionEnvironment(), SessionPaths(), LogindFacts(own=SSH))
    assert result.location is Location.SSH


def test_x_forwarding_is_not_the_desktop() -> None:
    env = SessionEnvironment(ssh=True, display="localhost:10.0", session_type="tty")
    result = assess_session(env, SessionPaths(), LogindFacts(display=GNOME, display_known=True))
    assert (result.kind, result.location, result.source) == (
        SessionKind.WAYLAND,
        Location.SSH,
        "logind",
    )
    assert any("X forwarding" in note for note in result.notes)


def test_text_console() -> None:
    result = _assess("linux-console", LogindFacts(display_known=True))
    assert (result.kind, result.location) == (SessionKind.NONE, Location.CONSOLE)


def test_console_from_logind_type() -> None:
    own = LogindSession(id="5", session_type="tty", session_class="user", seat="seat0")
    result = assess_session(SessionEnvironment(), SessionPaths(), LogindFacts(own=own))
    assert result.location is Location.CONSOLE


def test_service_without_anything_is_unknown_not_none() -> None:
    result = assess_session(SessionEnvironment(), SessionPaths(), LogindFacts())
    assert (result.kind, result.location, result.source) == (
        SessionKind.UNKNOWN,
        Location.ELSEWHERE,
        None,
    )


def test_service_finds_the_desktop_through_logind() -> None:
    result = assess_session(
        SessionEnvironment(), SessionPaths(), LogindFacts(display=X11_DESKTOP, display_known=True)
    )
    assert (result.kind, result.location, result.source) == (
        SessionKind.X11,
        Location.ELSEWHERE,
        "logind",
    )


def test_odd_logind_type_is_unknown() -> None:
    mir = LogindSession(id="9", session_type="mir")
    result = assess_session(SessionEnvironment(), SessionPaths(), LogindFacts(display=mir))
    assert result.kind is SessionKind.UNKNOWN
    assert result.source == "logind"


def test_xwayland_only_environment_is_still_a_wayland_desktop() -> None:
    env = SessionEnvironment(session_type="wayland", display=":0")
    result = assess_session(env, SOCKETS, LogindFacts(display=GNOME, display_known=True))
    assert result.kind is SessionKind.WAYLAND
    assert any("WAYLAND_DISPLAY is unset" in note for note in result.notes)


def test_nested_compositor_is_noted() -> None:
    env = SessionEnvironment(session_type="x11", display=":0", wayland_display="wayland-1")
    result = assess_session(env, SOCKETS, LogindFacts())
    assert result.kind is SessionKind.WAYLAND
    assert any("nested" in note for note in result.notes)


def test_stale_wayland_socket_is_noted() -> None:
    paths = SessionPaths(runtime_dir=PathState.DIRECTORY, wayland_socket=PathState.MISSING)
    result = _assess("hyprland", paths=paths)
    assert result.kind is SessionKind.WAYLAND
    assert any("does not exist" in note for note in result.notes)


def test_wayland_display_pointing_at_a_file_is_noted() -> None:
    paths = SessionPaths(runtime_dir=PathState.DIRECTORY, wayland_socket=PathState.OTHER)
    assert any("not a socket" in note for note in _assess("hyprland", paths=paths).notes)


def test_missing_runtime_dir_is_noted() -> None:
    paths = SessionPaths(runtime_dir=PathState.MISSING, wayland_socket=PathState.NOT_CHECKED)
    assert any("XDG_RUNTIME_DIR" in note for note in _assess("hyprland", paths=paths).notes)


def test_disagreement_with_logind_is_noted_not_resolved() -> None:
    result = _assess("gnome-x11", LogindFacts(display=GNOME, display_known=True))
    assert result.kind is SessionKind.X11
    assert result.source == "environment"
    assert any("logind reports" in note for note in result.notes)


def test_session_type_case_does_not_matter() -> None:
    env = SessionEnvironment(session_type="Wayland", display=":0")
    assert assess_session(env, SOCKETS, LogindFacts()).kind is SessionKind.WAYLAND


_text = st.none() | st.text(max_size=20)
_paths = st.builds(
    SessionPaths,
    runtime_dir=st.sampled_from(PathState),
    wayland_socket=st.sampled_from(PathState),
    x11_socket=st.sampled_from(PathState),
)
_sessions = st.none() | st.builds(
    LogindSession,
    id=st.just("1"),
    session_type=_text,
    remote=st.none() | st.booleans(),
)


@given(
    st.builds(
        SessionEnvironment,
        session_type=_text,
        wayland_display=_text,
        display=_text,
        ssh=st.booleans(),
    ),
    _paths,
    st.builds(LogindFacts, own=_sessions, display=_sessions, display_known=st.booleans()),
)
def test_known_kind_always_names_its_source(
    env: SessionEnvironment, paths: SessionPaths, logind: LogindFacts
) -> None:
    result = assess_session(env, paths, logind)
    assert (result.source is None) == (result.kind is SessionKind.UNKNOWN and not logind.display)
    if result.location is Location.SSH:
        assert result.source != "environment"
