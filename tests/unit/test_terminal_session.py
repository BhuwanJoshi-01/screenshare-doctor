"""The terminal session summary."""

from __future__ import annotations

from rich.console import Console

from screenshare_doctor.models import (
    FailureKind,
    LogindFacts,
    LogindSession,
    PathState,
    ProbeFailure,
    RedactionCount,
    SessionEnvironment,
    SessionFacts,
    SessionPaths,
    Snapshot,
)
from screenshare_doctor.reports.terminal import render_session

GNOME = LogindSession(
    id="63", session_type="wayland", session_class="user", seat="seat0", active=True
)
REAL_GNOME_ENV = SessionEnvironment(
    session_type="wayland",
    current_desktop="ubuntu:GNOME",
    session_desktop="ubuntu",
    desktop_session="ubuntu",
    wayland_display="wayland-0",
    display=":0",
    runtime_dir="/run/user/1000",
)
FOUND = SessionPaths(
    runtime_dir=PathState.DIRECTORY,
    wayland_socket=PathState.SOCKET,
    wayland_socket_path="/run/user/1000/wayland-0",
    x11_socket=PathState.SOCKET,
    x11_socket_path="/tmp/.X11-unix/X0",  # noqa: S108
)


def _render(snapshot: Snapshot) -> str:
    console = Console(width=200, record=True, color_system=None)
    with console.capture() as capture:
        render_session(snapshot, console)
    return capture.get()


def _snapshot(facts: SessionFacts, **kwargs: object) -> Snapshot:
    return Snapshot(
        tool_version="0.1.0", created_at="2026-11-03T10:00:00Z", session=facts, **kwargs
    )  # type: ignore[arg-type]


def test_real_gnome_session() -> None:
    out = _render(
        _snapshot(
            SessionFacts(REAL_GNOME_ENV, FOUND, LogindFacts(display=GNOME, display_known=True))
        )
    )
    assert "Session     Wayland (from this environment)" in out
    assert "Running in  a terminal of the desktop" in out
    assert (
        "Desktop     GNOME (XDG_CURRENT_DESKTOP=ubuntu:GNOME); the portal reads ubuntu, gnome"
        in out
    )
    assert "Wayland     WAYLAND_DISPLAY=wayland-0, socket found" in out
    assert "X11         DISPLAY=:0, socket found" in out
    assert "logind      session 63: wayland, user, seat0, active" in out
    assert "Notes" not in out
    assert "Could not check" not in out


def test_ssh_login() -> None:
    ssh = LogindSession(id="7", session_type="tty", session_class="user", remote=True, active=False)
    facts = SessionFacts(
        SessionEnvironment(session_type="tty", session_id="7", ssh=True),
        SessionPaths(runtime_dir=PathState.DIRECTORY),
        LogindFacts(own=ssh, display=GNOME, display_known=True),
    )
    out = _render(_snapshot(facts))
    assert "Wayland (from logind; this environment has no display)" in out
    assert "an SSH login" in out
    assert "this login: session 7: tty, user, remote, inactive" in out
    assert "WAYLAND_DISPLAY is unset" in out
    assert "unknown (XDG_CURRENT_DESKTOP is unset)" in out


def test_nothing_known_lists_the_failures() -> None:
    failure = ProbeFailure("loginctl show-user", FailureKind.NOT_FOUND, "loginctl was not found")
    out = _render(_snapshot(SessionFacts(), probe_failures=(failure,)))
    assert "unknown (neither the environment nor logind says)" in out
    assert "logind      no answer (see below)" in out
    assert "Could not check:\n  loginctl show-user: loginctl was not found" in out


def test_no_graphical_session() -> None:
    out = _render(_snapshot(SessionFacts(logind=LogindFacts(display_known=True))))
    assert "no graphical session (from logind" in out
    assert "no graphical session for this user" in out


def test_notes_and_ignored_names_are_shown() -> None:
    env = SessionEnvironment(
        session_type="wayland", current_desktop="ubuntu: GNOME", wayland_display="wayland-0"
    )
    paths = SessionPaths(runtime_dir=PathState.DIRECTORY, wayland_socket=PathState.MISSING)
    out = _render(_snapshot(SessionFacts(env, paths)))
    assert "socket missing" in out
    assert "names no desktop it knows" in out
    assert "Notes:\n  - WAYLAND_DISPLAY points to a socket that does not exist" in out


def test_ignored_desktop_entries_are_quoted() -> None:
    env = SessionEnvironment(current_desktop="KDE: GNOME", wayland_display="wayland-0")
    out = _render(_snapshot(SessionFacts(env)))
    assert "it ignores ' GNOME'" in out


def test_forwarded_x11_display() -> None:
    env = SessionEnvironment(display="localhost:10.0", ssh=True)
    assert "DISPLAY=localhost:10.0 (not a local display)" in _render(_snapshot(SessionFacts(env)))


def test_session_fallback_source_is_named() -> None:
    env = SessionEnvironment(session_desktop="plasma", wayland_display="wayland-0")
    assert "KDE Plasma (XDG_SESSION_DESKTOP)" in _render(_snapshot(SessionFacts(env)))


def test_markup_in_collected_values_is_printed_literally() -> None:
    env = SessionEnvironment(current_desktop="[bold red]x[/]", wayland_display="[link]")
    out = _render(_snapshot(SessionFacts(env)))
    assert "XDG_CURRENT_DESKTOP=[bold red]x[/]" in out
    assert "WAYLAND_DISPLAY=[link]" in out


def test_redactions_are_summarised() -> None:
    out = _render(
        _snapshot(
            SessionFacts(),
            redactions=(RedactionCount("home_path", 2), RedactionCount("user_name", 1)),
        )
    )
    assert "Redacted from this output: 2 home paths, 1 user name" in out


def test_snapshot_without_session_renders_unknowns() -> None:
    out = _render(Snapshot(tool_version="0.1.0", created_at="2026-11-03T10:00:00Z"))
    assert "Session     unknown" in out
