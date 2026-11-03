"""Terminal output: a short human summary of an already redacted snapshot.

Collected text is always added as plain ``Text``, never as Rich markup, so a desktop
name or path containing ``[bold]`` is printed as it is instead of being interpreted.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from screenshare_doctor.collectors.dbus import FRONTEND, MUTTER_SCREENCAST
from screenshare_doctor.desktops import DesktopFamily, DesktopIdentity, identify_desktop
from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    LogindSession,
    PackageFacts,
    PackageInfo,
    PackageState,
    PathState,
    PortalFiles,
    PortalObject,
    ScreenCastProperties,
    ServiceFacts,
    SessionEnvironment,
    SessionFacts,
    SessionPaths,
    Snapshot,
    UserService,
)
from screenshare_doctor.portal_paths import config_candidates
from screenshare_doctor.routes import (
    Agreement,
    PortalBehaviour,
    Route,
    RouteKind,
    RouteObservation,
    Rule,
    observe_route,
    parse_portal_version,
    public_interface,
    resolve_route,
)
from screenshare_doctor.screencast import cursor_mode_names, source_type_names
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


COMPONENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("portal frontend", "xdg-desktop-portal", ("xdg-desktop-portal.service",)),
    ("GNOME backend", "xdg-desktop-portal-gnome", ("xdg-desktop-portal-gnome.service",)),
    ("GTK backend", "xdg-desktop-portal-gtk", ("xdg-desktop-portal-gtk.service",)),
    ("KDE backend", "xdg-desktop-portal-kde", ("plasma-xdg-desktop-portal-kde.service",)),
    ("wlr backend", "xdg-desktop-portal-wlr", ("xdg-desktop-portal-wlr.service",)),
    ("Hyprland backend", "xdg-desktop-portal-hyprland", ("xdg-desktop-portal-hyprland.service",)),
    ("PipeWire", "pipewire", ("pipewire.socket", "pipewire.service")),
    ("WirePlumber", "wireplumber", ("wireplumber.service",)),
)
"""Component, package and user units, in the order a screen-sharing request uses them."""

_ACTIVATION_VARIABLES = (
    ("XDG_CURRENT_DESKTOP", "current_desktop"),
    ("XDG_SESSION_TYPE", "session_type"),
    ("WAYLAND_DISPLAY", "wayland_display"),
    ("DISPLAY", "display"),
)

_PACKAGE_SOURCE = {
    "dpkg": "Packages from dpkg.",
    "rpm": "Packages from rpm.",
    "pacman": "Packages from pacman.",
    "files": (
        "No package manager answered; packages were judged by their programs only, "
        "so unknown may mean not installed."
    ),
}


def render_services(snapshot: Snapshot, console: Console) -> None:
    """Packages and user services per component, then the user manager's environment."""
    console.print(Text(f"screenshare-doctor {snapshot.tool_version}: services", style="bold"))
    console.print()
    packages = snapshot.packages or PackageFacts()
    services = snapshot.services or ServiceFacts()
    table = Table(box=None, show_edge=False, pad_edge=False, header_style="bold")
    table.add_column("Component")
    table.add_column("Package")
    table.add_column("User service")
    package_by_name = {package.name: package for package in packages.packages}
    unit_by_name = {service.unit: service for service in services.services or ()}
    for label, package_name, units in COMPONENTS:
        table.add_row(
            Text(label),
            Text(_package_cell(package_by_name.get(package_name))),
            Text(_units_cell(units, unit_by_name, known=services.services is not None)),
        )
    console.print(table)
    if packages.source in _PACKAGE_SOURCE:
        console.print(Text(_PACKAGE_SOURCE[packages.source], style="dim"))
    console.print(
        Text(
            'Portals are started on demand: "not running" is normal until an app asks for one.',
            style="dim",
        )
    )
    console.print()
    console.print(
        Text("Activation environment (what portals started by the user manager see):", style="bold")
    )
    shell = snapshot.session.environment if snapshot.session else None
    activation = services.activation_environment
    if activation is None:
        console.print(Text("  not read (see below)"))
    else:
        values = [_value(getattr(activation, attribute)) for _, attribute in _ACTIVATION_VARIABLES]
        width = max(len(value) for value in values)
        for name, attribute in _ACTIVATION_VARIABLES:
            console.print(Text(_activation_line(name, attribute, activation, shell, width)))
    _render_failures(snapshot, console)


def _package_cell(package: PackageInfo | None) -> str:
    if package is None or package.state is PackageState.UNKNOWN:
        return "unknown"
    if package.state is PackageState.NOT_INSTALLED:
        return "not installed"
    if package.state is PackageState.BROKEN:
        return f"broken install ({package.version})" if package.version else "broken install"
    return package.version or "installed"


def _units_cell(units: tuple[str, ...], by_name: dict[str, UserService], *, known: bool) -> str:
    if not known:
        return "unknown"
    states = [_unit_state(by_name.get(unit)) for unit in units]
    if len(units) == 1:
        return states[0]
    return "; ".join(
        f"{unit.rsplit('.', 1)[1]}: {state}" for unit, state in zip(units, states, strict=True)
    )


def _unit_state(service: UserService | None) -> str:
    if service is None or service.load_state is None:
        return "unknown"
    if service.load_state == "not-found":
        return "no unit"
    if service.load_state == "masked":
        return "masked"
    if service.active_state == "active":
        return f"running ({service.unit_file_state})" if service.unit_file_state else "running"
    if service.active_state == "inactive":
        return "not running"
    if service.active_state == "failed":
        return "failed"
    return service.active_state or "unknown"


def _value(value: str | None) -> str:
    return value if value is not None else "unset"


def _activation_line(
    name: str,
    attribute: str,
    activation: SessionEnvironment,
    shell: SessionEnvironment | None,
    width: int,
) -> str:
    value = getattr(activation, attribute)
    if shell is None or not (shell.wayland_display or shell.display):
        return f"  {name:<21}{_value(value)}"  # not run from the desktop: nothing to compare
    shell_value = getattr(shell, attribute)
    if shell_value == value:
        comparison = "(same as this shell)"
    else:
        comparison = f"(this shell: {_value(shell_value)})"
    return f"  {name:<21}{_value(value):<{width}}  {comparison}"


_BUS_LABELS = {
    FRONTEND: "portal frontend",
    "org.freedesktop.impl.portal.desktop.gnome": "GNOME backend",
    "org.freedesktop.impl.portal.desktop.gtk": "GTK backend",
    "org.freedesktop.impl.portal.desktop.kde": "KDE backend",
    "org.freedesktop.impl.portal.desktop.wlr": "wlr backend",
    "org.freedesktop.impl.portal.desktop.hyprland": "Hyprland backend",
    MUTTER_SCREENCAST: "Mutter ScreenCast",
}


def render_dbus(snapshot: Snapshot, console: Console) -> None:
    """Which portal names run or can start, and what the running ones offer for ScreenCast."""
    console.print(Text(f"screenshare-doctor {snapshot.tool_version}: D-Bus", style="bold"))
    console.print()
    dbus = snapshot.dbus or DbusFacts()
    reachable = {True: "reachable", False: "not reachable", None: "unknown"}[dbus.reachable]
    console.print(_row("Session bus", reachable))
    if dbus.names:
        console.print()
        objects = {portal.name: portal for portal in dbus.objects}
        table = Table(box=None, show_edge=False, pad_edge=False, header_style="bold")
        for column in ("Component", "Running", "Can start", "ScreenCast"):
            table.add_column(column)
        for name in dbus.names:
            table.add_row(
                Text(_BUS_LABELS.get(name.name, name.name)),
                Text(_yes_no(name.running)),
                Text(_yes_no(name.activatable)),
                Text(_screencast_cell(name, objects.get(name.name))),
            )
        console.print(table)
        console.print(
            Text(
                "Only services that were already running were contacted; nothing was started.",
                style="dim",
            )
        )
    _render_failures(snapshot, console)


def _yes_no(value: bool | None) -> str:
    return {True: "yes", False: "no", None: "unknown"}[value]


def _screencast_cell(name: BusName, portal: PortalObject | None) -> str:
    if name.running is not True:
        return "-"
    if portal is None or (portal.interfaces is None and portal.screencast is None):
        return "unknown (see below)"
    if portal.screencast is None:
        if portal.interfaces is not None and not any(
            interface.endswith(".ScreenCast") for interface in portal.interfaces
        ):
            return "not implemented"
        return "unknown (see below)"
    return _describe_screencast(portal.screencast)


def _describe_screencast(properties: ScreenCastProperties) -> str:
    parts = [f"version {properties.version}" if properties.version is not None else "version ?"]
    if properties.source_types is not None:
        sources = source_type_names(properties.source_types)
        parts.append("sources: " + (", ".join(sources) if sources else "none"))
    if properties.cursor_modes is not None:
        modes = cursor_mode_names(properties.cursor_modes)
        parts.append("cursor: " + (", ".join(modes) if modes else "none"))
    return "; ".join(parts)


_AGREEMENT = {
    Agreement.CONSISTENT: "consistent with the prediction",
    Agreement.STARTS_ON_DEMAND: (
        "not running now; the bus can start it on demand (normal for portals)"
    ),
    Agreement.CANNOT_START: "not running, and the bus cannot start it: requests will fail",
    Agreement.MISSING_INTERFACE: "running, but it does not implement the interface",
    Agreement.NOT_OFFERED: "the frontend does not offer the interface",
    Agreement.OFFERED_WITHOUT_BACKEND: (
        "the frontend offers the interface although no backend was predicted"
    ),
    Agreement.NOT_CHECKED: (
        "not checked (the backend's bus name is not probed, or the bus did not answer)"
    ),
}


def portal_version(snapshot: Snapshot) -> str | None:
    """The installed xdg-desktop-portal version, when the package manager reported it."""
    for package in (snapshot.packages or PackageFacts()).packages:
        if package.name == "xdg-desktop-portal" and package.state is PackageState.INSTALLED:
            return package.version
    return None


def render_route(snapshot: Snapshot, interface: str, console: Console) -> Route:
    """Explain the predicted backend for ``interface`` (an ``impl`` name); returns the route."""
    files = snapshot.portal_files or PortalFiles()
    version = portal_version(snapshot)
    behaviour = PortalBehaviour(parse_portal_version(version))
    route = resolve_route(interface, files, behaviour)
    observation = observe_route(route, snapshot.dbus)
    short = interface.rsplit(".", 1)[-1]
    console.print(
        Text(f"screenshare-doctor {snapshot.tool_version}: route for {short}", style="bold")
    )
    console.print()
    console.print(_row("Interface", f"{short} ({public_interface(interface)})"))
    console.print(_row("Predicted", _predicted(route)))
    console.print(_row("Decided by", _decided_by(route, files)))
    console.print(_row("Portal", _behaviour_line(version, behaviour)))
    console.print(_row("Desktops", _desktops_line(files)))
    console.print(_row("On D-Bus", _observed(route, observation)))
    if route.trace:
        console.print()
        console.print(Text("How it was decided:", style="bold"))
        for number, step in enumerate(route.trace, start=1):
            console.print(Text(f"  {number}. {step}"))
    if files.config_directories:
        console.print()
        console.print(Text("Configuration search order (highest priority first):", style="bold"))
        for line in _search_lines(files):
            console.print(Text(f"  {line}"))
    if route.uncertain:
        console.print()
        console.print(Text("The prediction may be wrong because:", style="bold"))
        for reason in route.uncertain:
            console.print(Text(f"  - {reason}"))
    _render_failures(snapshot, console)
    return route


def _predicted(route: Route) -> str:
    if route.kind is RouteKind.DISABLED:
        return "none: a configuration disables this interface"
    if route.backend is None:
        return "none: no installed backend implements it, so apps cannot use it"
    return f"{route.backend.source} ({route.backend.dbus_name})"


def _decided_by(route: Route, files: PortalFiles) -> str:
    if route.rule is Rule.USE_IN:
        return (
            "the deprecated UseIn key of the backend's .portal file (no portals.conf entry matched)"
        )
    if route.rule is Rule.GTK_FALLBACK:
        return "the last-resort gtk fallback (nothing else matched)"
    if route.rule is Rule.NO_MATCH:
        return "nothing: no configuration entry or fallback matched"
    conf = next((c for c in files.configs if c.path == route.config), None)
    key = route.interface if route.rule in {Rule.INTERFACE, Rule.NONE} else "default"
    if conf is not None:
        entries = dict(conf.preferred)
        if route.rule is Rule.NONE and route.interface not in entries:
            key = "default"
        if key in entries:
            return f"{key}={';'.join(entries[key])} in {conf.path}"
    return f"{key} in {route.config}"


def _behaviour_line(version: str | None, behaviour: PortalBehaviour) -> str:
    if version is None:
        return (
            "xdg-desktop-portal version unknown; the newest rules (1.21.1 and later) were applied"
        )
    effective = behaviour.effective
    if behaviour.falls_through:
        rules = "1.21.1 and later"
    elif behaviour.all_descriptor_dirs:
        rules = "1.20.1 to 1.21.0"
    elif behaviour.ordered_lists:
        rules = "1.19 to 1.20.0"
    elif behaviour.reads_config:
        rules = "1.17 and 1.18"
    else:
        rules = "before 1.17"
    shown = ".".join(str(part) for part in effective)
    return f"xdg-desktop-portal {version} (selection rules of {rules}; read as {shown})"


def _desktops_line(files: PortalFiles) -> str:
    names = ", ".join(files.desktops) if files.desktops else "none"
    whose = "the user manager" if files.variables_from == "user manager" else files.variables_from
    return f"{names} (XDG_CURRENT_DESKTOP of {whose})"


def _observed(route: Route, observation: RouteObservation) -> str:
    text = _AGREEMENT[observation.agreement]
    if observation.agreement is Agreement.CONSISTENT and route.backend is not None:
        return f"{route.backend.source} is running and implements it; the frontend offers it"
    return text


def _search_lines(files: PortalFiles) -> list[str]:
    by_path = {conf.path: conf for conf in files.configs}
    unreadable = set(files.unreadable)
    lines: list[str] = []
    for index, directory in enumerate(files.config_directories, start=1):
        found = []
        for path in config_candidates(directory, files.desktops):
            name = path.rsplit("/", 1)[1]
            if path in unreadable:
                found.append(f"{name} (unreadable)")
            elif path in by_path:
                conf = by_path[path]
                found.append(name if conf.usable else f"{name} (ignored: {conf.error})")
        lines.append(f"{index:>2}. {directory}: {', '.join(found) if found else 'nothing'}")
    return lines


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
