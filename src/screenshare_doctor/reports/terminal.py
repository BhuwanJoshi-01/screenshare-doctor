"""Terminal output: a short human summary of an already redacted snapshot.

Collected text is always added as plain ``Text``, never as Rich markup, so a desktop
name or path containing ``[bold]`` is printed as it is instead of being interpreted.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from screenshare_doctor.desktops import DesktopFamily, DesktopIdentity, identify_desktop
from screenshare_doctor.models import (
    LogindSession,
    PathState,
    SessionEnvironment,
    SessionFacts,
    SessionPaths,
    Snapshot,
)
from screenshare_doctor.session import Location, SessionAssessment, SessionKind, assess_session

_LABEL_WIDTH = 12

_KIND = {
    SessionKind.WAYLAND: "Wayland",
    SessionKind.X11: "X11",
    SessionKind.NONE: "no graphical session",
    SessionKind.UNKNOWN: "unknown",
}

_LOCATION = {
    Location.DESKTOP: "a terminal of the desktop",
    Location.SSH: "an SSH login",
    Location.CONSOLE: "a text console",
    Location.ELSEWHERE: "outside the desktop (a service, a container or the user manager)",
}

_FAMILY = {
    DesktopFamily.GNOME: "GNOME",
    DesktopFamily.KDE: "KDE Plasma",
    DesktopFamily.HYPRLAND: "Hyprland",
    DesktopFamily.WLROOTS: "a wlroots compositor",
    DesktopFamily.OTHER: "a desktop without its own checks yet",
    DesktopFamily.UNKNOWN: "unknown",
}

_PATH = {
    PathState.SOCKET: "socket found",
    PathState.DIRECTORY: "found",
    PathState.OTHER: "exists but is not a socket",
    PathState.MISSING: "socket missing",
    PathState.UNREADABLE: "could not be checked (permission denied)",
    PathState.NOT_CHECKED: "not checked",
}

_REDACTION_NAMES = {
    "home_path": ("home path", "home paths"),
    "user_name": ("user name", "user names"),
    "host_name": ("host name", "host names"),
    "secret_value": ("secret value", "secret values"),
    "url_credentials": ("URL credential", "URL credentials"),
    "token": ("token", "tokens"),
}


def render_session(snapshot: Snapshot, console: Console) -> None:
    """The session summary: kind, location, desktop, sockets, logind, notes, failures."""
    console.print(Text(f"screenshare-doctor {snapshot.tool_version}: session", style="bold"))
    console.print()
    facts = snapshot.session or SessionFacts()
    assessment = assess_session(facts.environment, facts.paths, facts.logind)
    identity = identify_desktop(facts.environment)
    console.print(_row("Session", _session_line(assessment)))
    console.print(_row("Running in", _LOCATION[assessment.location]))
    console.print(_row("Desktop", _desktop_line(identity, facts.environment)))
    console.print(_row("Wayland", _wayland_line(facts.environment, facts.paths)))
    console.print(_row("X11", _x11_line(facts.environment, facts.paths)))
    console.print(_row("logind", _logind_line(facts)))
    if assessment.notes:
        console.print()
        console.print(Text("Notes:", style="bold"))
        for note in assessment.notes:
            console.print(Text(f"  - {note}"))
    _render_failures(snapshot, console)


def _row(label: str, value: str) -> Text:
    return Text.assemble((f"{label:<{_LABEL_WIDTH}}", "bold"), value)


def _session_line(assessment: SessionAssessment) -> str:
    kind = _KIND[assessment.kind]
    if assessment.source == "environment":
        return f"{kind} (from this environment)"
    if assessment.source == "logind":
        return f"{kind} (from logind; this environment has no display)"
    return f"{kind} (neither the environment nor logind says)"


def _desktop_line(identity: DesktopIdentity, env: SessionEnvironment) -> str:
    if identity.source is None:
        if env.current_desktop is None:
            return "unknown (XDG_CURRENT_DESKTOP is unset)"
        return f"unknown (XDG_CURRENT_DESKTOP={env.current_desktop} names no desktop it knows)"
    line = f"{_FAMILY[identity.family]} ({identity.source}"
    if identity.source == "XDG_CURRENT_DESKTOP":
        line += f"={env.current_desktop}"
    line += ")"
    if identity.portal_names:
        line += f"; the portal reads {', '.join(identity.portal_names)}"
    if identity.ignored:
        line += f"; it ignores {', '.join(repr(name) for name in identity.ignored)}"
    return line


def _wayland_line(env: SessionEnvironment, paths: SessionPaths) -> str:
    if env.wayland_display is None:
        return "WAYLAND_DISPLAY is unset"
    return f"WAYLAND_DISPLAY={env.wayland_display}, {_PATH[paths.wayland_socket]}"


def _x11_line(env: SessionEnvironment, paths: SessionPaths) -> str:
    if env.display is None:
        return "DISPLAY is unset"
    if paths.x11_socket_path is None:
        return f"DISPLAY={env.display} (not a local display)"
    return f"DISPLAY={env.display}, {_PATH[paths.x11_socket]}"


def _logind_line(facts: SessionFacts) -> str:
    logind = facts.logind
    if logind.display is not None:
        line = _describe(logind.display)
        if logind.own is not None and logind.own is not logind.display:
            line += f"; this login: {_describe(logind.own)}"
        return line
    if logind.display_known:
        own = f"; this login: {_describe(logind.own)}" if logind.own else ""
        return f"no graphical session for this user{own}"
    return "no answer (see below)"


def _describe(session: LogindSession) -> str:
    parts = [session.session_type or "type unknown"]
    if session.session_class:
        parts.append(session.session_class)
    if session.seat:
        parts.append(session.seat)
    if session.remote:
        parts.append("remote")
    if session.active is not None:
        parts.append("active" if session.active else "inactive")
    return f"session {session.id}: {', '.join(parts)}"


def redaction_line(snapshot: Snapshot) -> str | None:
    """'Redacted from this output: 3 home paths, 1 secret value', or None if nothing was."""
    if not snapshot.redactions:
        return None
    parts = []
    for item in snapshot.redactions:
        singular, plural = _REDACTION_NAMES.get(item.kind, (item.kind, item.kind))
        parts.append(f"{item.count} {singular if item.count == 1 else plural}")
    return "Redacted from this output: " + ", ".join(parts)


def _render_failures(snapshot: Snapshot, console: Console) -> None:
    if snapshot.probe_failures:
        console.print()
        console.print(Text("Could not check:", style="bold"))
        for failure in snapshot.probe_failures:
            console.print(Text(f"  {failure.probe}: {failure.detail}"))
    line = redaction_line(snapshot)
    if line:
        console.print()
        console.print(Text(line, style="dim"))
