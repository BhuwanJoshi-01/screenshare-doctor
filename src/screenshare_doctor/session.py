"""What kind of session this is, decided from the collected facts only.

Two questions are kept apart. ``kind``: is the user's desktop a Wayland or an X11
session, or is there none? ``location``: does the tool run inside that desktop, over
SSH, on a text console or somewhere else (a service, a container)? A tool run over SSH
can still describe the desktop through logind, but cannot see the desktop's variables.

The tool's own environment wins when it holds a display, because that is what the apps
started from here will use. logind is the fallback, and disagreements between the two
are listed as ``notes`` instead of being resolved silently.

Pure functions: nothing here reads the environment, files or commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from screenshare_doctor.desktops import ascii_lower
from screenshare_doctor.models import LogindFacts, PathState, SessionEnvironment, SessionPaths


class SessionKind(StrEnum):
    """The user's desktop session."""

    WAYLAND = "wayland"
    X11 = "x11"
    NONE = "none"
    """logind answered and knows no graphical session for this user."""
    UNKNOWN = "unknown"


class Location(StrEnum):
    """Where the tool runs, relative to the desktop."""

    DESKTOP = "desktop"
    SSH = "ssh"
    CONSOLE = "console"
    ELSEWHERE = "elsewhere"
    """No display variables, not SSH, not a console: a service, cron, a container…"""


@dataclass(frozen=True, slots=True)
class SessionAssessment:
    """The answer, with ``source`` saying whether it came from the ``environment`` or
    ``logind`` (``None`` when neither knew)."""

    kind: SessionKind
    location: Location
    source: str | None
    notes: tuple[str, ...] = ()


def assess_session(
    env: SessionEnvironment, paths: SessionPaths, logind: LogindFacts
) -> SessionAssessment:
    """Decide the session kind and the tool's location; list what does not add up."""
    notes: list[str] = []
    declared = ascii_lower(env.session_type) if env.session_type else None
    own = logind.own

    if env.ssh or (own is not None and own.remote):
        location = Location.SSH
    elif env.wayland_display or env.display:
        location = Location.DESKTOP
    elif declared == "tty" or (own is not None and own.session_type == "tty"):
        location = Location.CONSOLE
    else:
        location = Location.ELSEWHERE

    env_kind: SessionKind | None = None
    if location is Location.DESKTOP:
        # XDG_SESSION_TYPE=wayland with only DISPLAY set is a Wayland desktop seen through
        # Xwayland; the note below says so.
        wayland = env.wayland_display is not None or declared == "wayland"
        env_kind = SessionKind.WAYLAND if wayland else SessionKind.X11
        notes += _environment_notes(env, declared, paths)
    elif location is Location.SSH and env.display:
        notes.append(
            "DISPLAY is set in an SSH login (X forwarding); it is not the desktop's display"
        )

    logind_kind = _logind_kind(logind)
    if env_kind is not None:
        if logind_kind in {SessionKind.WAYLAND, SessionKind.X11} and logind_kind != env_kind:
            notes.append(
                f"logind reports the graphical session as {logind_kind}, "
                f"but this environment is {env_kind}"
            )
        return SessionAssessment(env_kind, location, "environment", tuple(notes))
    if logind_kind is not None:
        return SessionAssessment(logind_kind, location, "logind", tuple(notes))
    return SessionAssessment(SessionKind.UNKNOWN, location, None, tuple(notes))


def _environment_notes(
    env: SessionEnvironment, declared: str | None, paths: SessionPaths
) -> list[str]:
    notes: list[str] = []
    if declared == "wayland" and not env.wayland_display:
        notes.append(
            "XDG_SESSION_TYPE is wayland but WAYLAND_DISPLAY is unset, "
            "so apps started from here fall back to X11"
        )
    if declared == "x11" and env.wayland_display:
        notes.append("XDG_SESSION_TYPE is x11 but WAYLAND_DISPLAY is set (a nested compositor?)")
    if env.wayland_display and paths.wayland_socket is PathState.MISSING:
        notes.append(
            "WAYLAND_DISPLAY points to a socket that does not exist; "
            "the variables may be left over from an earlier session"
        )
    if env.wayland_display and paths.wayland_socket is PathState.OTHER:
        notes.append("WAYLAND_DISPLAY points to something that is not a socket")
    if paths.runtime_dir is PathState.MISSING:
        notes.append("XDG_RUNTIME_DIR does not exist")
    return notes


def _logind_kind(logind: LogindFacts) -> SessionKind | None:
    display = logind.display
    if display is not None:
        if display.session_type == "wayland":
            return SessionKind.WAYLAND
        if display.session_type == "x11":
            return SessionKind.X11
        return SessionKind.UNKNOWN
    if logind.display_known:
        return SessionKind.NONE
    return None
