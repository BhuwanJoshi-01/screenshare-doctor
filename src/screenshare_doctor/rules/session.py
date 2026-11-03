"""The session layer: what kind of session this is and what the portal will see of it."""

from __future__ import annotations

from collections.abc import Iterator

from screenshare_doctor.desktops import identify_desktop
from screenshare_doctor.models import (
    Confidence,
    Evidence,
    Finding,
    Layer,
    PathState,
    SessionEnvironment,
    Severity,
    Snapshot,
    Status,
)
from screenshare_doctor.rules.catalog import RULES
from screenshare_doctor.rules.engine import RuleContext
from screenshare_doctor.session import Location, SessionKind, assess_session

ENV = "environment"


@RULES.rule("SSD-SESSION-001", "The desktop session is Wayland", layer=Layer.SESSION)
def session_type(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the user's desktop is a Wayland session.

    Portal screen sharing is the Wayland way: apps cannot read the screen themselves.
    The answer comes from the tool's own environment when it runs in the desktop, and
    from logind otherwise. On X11 apps capture the screen directly, so the portal
    checks here mostly do not apply; with no graphical session there is nothing to
    share.
    """
    facts = snapshot.session
    if facts is None:
        return
    result = assess_session(facts.environment, facts.paths, facts.logind)
    display = facts.logind.display
    evidence = (
        Evidence(ENV, "XDG_SESSION_TYPE", facts.environment.session_type),
        Evidence(ENV, "WAYLAND_DISPLAY", facts.environment.wayland_display),
        Evidence("logind", "Type", display.session_type if display else None),
    )
    confidence = Confidence.HIGH if result.source == "environment" else Confidence.MEDIUM
    if result.kind is SessionKind.WAYLAND:
        yield Finding(
            id="SSD-SESSION-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=confidence,
            summary="Wayland session",
            reason=f"Decided from {result.source}.",
            evidence=evidence,
        )
    elif result.kind is SessionKind.X11:
        yield Finding(
            id="SSD-SESSION-001",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=confidence,
            summary="X11 session",
            reason=(
                "On X11 apps capture the screen themselves, without the portal; most checks "
                "of this tool are about Wayland screen sharing."
            ),
            evidence=evidence,
            recommended_action=(
                "If you meant to use Wayland, pick the Wayland session on the login screen."
            ),
            verify_command="echo $XDG_SESSION_TYPE",
        )
    elif result.kind is SessionKind.NONE:
        yield Finding(
            id="SSD-SESSION-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="No graphical session",
            reason="logind knows no graphical session for this user: there is no screen to share.",
            evidence=evidence,
            recommended_action="Log in to a desktop session and run the check from there.",
            verify_command="loginctl show-user $(id -u) -p Display",
        )
    else:
        yield Finding(
            id="SSD-SESSION-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="The session type could not be told",
            reason="Neither the environment nor logind says what kind of session this is.",
            evidence=evidence,
            recommended_action="Run the check from a terminal of the desktop.",
        )


@RULES.rule(
    "SSD-SESSION-002", "Apps started here can reach the Wayland display", layer=Layer.SESSION
)
def wayland_display(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether WAYLAND_DISPLAY is set and its socket exists, for apps started from here.

    An app without WAYLAND_DISPLAY runs through XWayland and can only see X11 windows;
    a socket that no longer exists means the variables are left over from an earlier
    session (a long-running tmux, for one). Only judged when the tool runs in the
    desktop: elsewhere its own variables say nothing about the desktop's.
    """
    facts = snapshot.session
    if facts is None:
        return
    result = assess_session(facts.environment, facts.paths, facts.logind)
    if result.kind is not SessionKind.WAYLAND:
        return
    env, paths = facts.environment, facts.paths
    evidence = (
        Evidence(ENV, "WAYLAND_DISPLAY", env.wayland_display),
        Evidence("stat", "wayland socket", paths.wayland_socket.value),
    )
    if result.location is not Location.DESKTOP:
        yield Finding(
            id="SSD-SESSION-002",
            status=Status.NOT_APPLICABLE,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Not run from the desktop",
            reason=(
                f"The tool runs in {result.location.value}; "
                "its display variables are not the desktop's."
            ),
            evidence=evidence,
        )
        return
    if env.wayland_display is None:
        yield Finding(
            id="SSD-SESSION-002",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            summary="WAYLAND_DISPLAY is not set here",
            reason=(
                "The session is Wayland, but apps started from this shell fall back to X11 "
                "(XWayland) and can only share X11 windows."
            ),
            evidence=evidence,
            recommended_action="Start apps from the desktop's launcher or a fresh terminal of it.",
            verify_command="echo $WAYLAND_DISPLAY",
        )
    elif paths.wayland_socket in (PathState.MISSING, PathState.OTHER):
        yield Finding(
            id="SSD-SESSION-002",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="The Wayland socket does not exist",
            reason=(
                f"WAYLAND_DISPLAY={env.wayland_display}, but {paths.wayland_socket_path} is "
                f"{paths.wayland_socket.value}: the variables are left over from another session."
            ),
            evidence=evidence,
            recommended_action="Open a new terminal from the running desktop (or restart tmux).",
            verify_command='ls -l "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"',
        )
    elif paths.wayland_socket is PathState.SOCKET:
        yield Finding(
            id="SSD-SESSION-002",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="The Wayland display is reachable",
            reason=f"{paths.wayland_socket_path} is a socket.",
            evidence=evidence,
        )
    else:
        yield Finding(
            id="SSD-SESSION-002",
            status=Status.UNKNOWN,
            severity=Severity.LOW,
            confidence=Confidence.LOW,
            summary="The Wayland socket could not be checked",
            reason=f"Its state is {paths.wayland_socket.value}.",
            evidence=evidence,
        )


def _portal_environment(snapshot: Snapshot) -> tuple[SessionEnvironment | None, str]:
    services = snapshot.services
    if services is not None and services.activation_environment is not None:
        return services.activation_environment, "the user manager"
    if snapshot.session is not None:
        return snapshot.session.environment, "this shell"
    return None, ""


@RULES.rule("SSD-SESSION-003", "The portal knows which desktop this is", layer=Layer.SESSION)
def desktop_name(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the portal's XDG_CURRENT_DESKTOP names the desktop.

    The portal picks <desktop>-portals.conf from it; without a name only a general
    portals.conf, the deprecated UseIn key or the gtk fallback can choose a backend,
    and gtk has no ScreenCast. Entries with characters other than letters, digits, -
    and _ are dropped by the portal. Read from the user manager's environment, which is
    the one the portal runs with.
    """
    env, whose = _portal_environment(snapshot)
    if env is None:
        return
    identity = identify_desktop(env)
    evidence = (Evidence(f"environment of {whose}", "XDG_CURRENT_DESKTOP", env.current_desktop),)
    if env.current_desktop is None:
        yield Finding(
            id="SSD-SESSION-003",
            status=Status.WARN,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="XDG_CURRENT_DESKTOP is not set for the portal",
            reason=(
                f"It is unset in the environment of {whose}, so the portal cannot read "
                "<desktop>-portals.conf and may end up without a ScreenCast backend."
            ),
            evidence=evidence,
            recommended_action=(
                "Export it from your session startup, e.g. for Hyprland or sway: "
                "dbus-update-activation-environment --systemd XDG_CURRENT_DESKTOP WAYLAND_DISPLAY"
            ),
            verify_command="systemctl --user show-environment | grep XDG_CURRENT_DESKTOP",
        )
    elif identity.ignored:
        yield Finding(
            id="SSD-SESSION-003",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            summary="The portal ignores part of XDG_CURRENT_DESKTOP",
            reason=(
                "These entries contain characters the portal does not accept and are dropped: "
                + ", ".join(repr(name) for name in identity.ignored)
            ),
            evidence=evidence,
            recommended_action="Use only letters, digits, - and _ between the colons (no spaces).",
            verify_command="systemctl --user show-environment | grep XDG_CURRENT_DESKTOP",
        )
    else:
        yield Finding(
            id="SSD-SESSION-003",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary=f"The portal reads the desktop names {', '.join(identity.portal_names)}",
            reason=f"From XDG_CURRENT_DESKTOP of {whose}.",
            evidence=evidence,
            limitations=(
                ("None of these names is a desktop this tool has defaults for.",)
                if identity.source != "XDG_CURRENT_DESKTOP"
                else ()
            ),
        )


@RULES.rule("SSD-SESSION-004", "Portals see the session's display variables", layer=Layer.SESSION)
def activation_environment(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the user manager, which starts the portals, has the desktop's variables.

    Portals are started by the user manager and inherit its environment, not the
    terminal's. A backend without WAYLAND_DISPLAY cannot reach the compositor; a portal
    with another XDG_CURRENT_DESKTOP picks another backend. Compositors started outside
    a desktop session (Hyprland, sway from a TTY) must export them themselves. Compared
    only when the tool runs in the desktop, whose variables are then known.
    """
    session, services = snapshot.session, snapshot.services
    if session is None or services is None:
        return
    result = assess_session(session.environment, session.paths, session.logind)
    if result.kind is not SessionKind.WAYLAND or result.location is not Location.DESKTOP:
        return
    shell, activation = session.environment, services.activation_environment
    if activation is None:
        yield Finding(
            id="SSD-SESSION-004",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="The user manager's environment could not be read",
            reason="Without it, what the portals see cannot be compared with this session.",
        )
        return
    evidence = (
        Evidence("user manager", "WAYLAND_DISPLAY", activation.wayland_display),
        Evidence(ENV, "WAYLAND_DISPLAY", shell.wayland_display),
        Evidence("user manager", "XDG_CURRENT_DESKTOP", activation.current_desktop),
        Evidence(ENV, "XDG_CURRENT_DESKTOP", shell.current_desktop),
    )
    fix = (
        "Export the variables to the user manager from your session startup: "
        "dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP, "
        "then restart the portals (systemctl --user restart xdg-desktop-portal) or log in again."
    )
    verify = "systemctl --user show-environment | grep -E '^(WAYLAND_DISPLAY|XDG_CURRENT_DESKTOP)='"
    if shell.wayland_display and activation.wayland_display is None:
        yield Finding(
            id="SSD-SESSION-004",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="Portals do not know the Wayland display",
            reason=(
                "WAYLAND_DISPLAY is set in this session but not in the user manager, so a "
                "portal backend it starts cannot connect to the compositor."
            ),
            evidence=evidence,
            recommended_action=fix,
            verify_command=verify,
        )
    elif shell.current_desktop != activation.current_desktop:
        yield Finding(
            id="SSD-SESSION-004",
            status=Status.WARN,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="Portals see another desktop name than this session",
            reason=(
                f"XDG_CURRENT_DESKTOP is {shell.current_desktop!r} here but "
                f"{activation.current_desktop!r} in the user manager; the portal picks its "
                "backend from the latter."
            ),
            evidence=evidence,
            recommended_action=fix,
            verify_command=verify,
        )
    else:
        yield Finding(
            id="SSD-SESSION-004",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Portals see the same desktop and display",
            reason=(
                "WAYLAND_DISPLAY and XDG_CURRENT_DESKTOP match between this session "
                "and the user manager."
            ),
            evidence=evidence,
        )
