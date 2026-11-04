"""The D-Bus and portal layers: the session bus, the frontend, the route and its backend."""

from __future__ import annotations

from collections.abc import Iterator

from screenshare_doctor.collectors.dbus import FRONTEND, SCREENCAST
from screenshare_doctor.models import (
    Confidence,
    Evidence,
    Finding,
    Layer,
    PackageState,
    PortalFiles,
    PortalObject,
    Severity,
    Snapshot,
    Status,
)
from screenshare_doctor.routes import (
    Agreement,
    PortalBehaviour,
    Route,
    RouteKind,
    observe_route,
    parse_portal_version,
    resolve_route,
)
from screenshare_doctor.rules.catalog import RULES
from screenshare_doctor.rules.engine import RuleContext
from screenshare_doctor.screencast import source_type_names

IMPL_SCREENCAST = "org.freedesktop.impl.portal.ScreenCast"
PORTAL_UNITS = ("xdg-desktop-portal.service",)


def _bus_cause(snapshot: Snapshot) -> str | None:
    """``SSD-DBUS-001`` when the session bus did not answer, so findings can follow from it."""
    dbus = snapshot.dbus
    return "SSD-DBUS-001" if dbus is not None and dbus.reachable is not True else None


def portal_version(snapshot: Snapshot) -> str | None:
    for package in snapshot.packages.packages if snapshot.packages else ():
        if package.name == "xdg-desktop-portal" and package.state is PackageState.INSTALLED:
            return package.version
    return None


def screencast_route(snapshot: Snapshot) -> Route | None:
    files: PortalFiles | None = snapshot.portal_files
    if files is None:
        return None
    behaviour = PortalBehaviour(parse_portal_version(portal_version(snapshot)))
    return resolve_route(IMPL_SCREENCAST, files, behaviour)


@RULES.rule("SSD-DBUS-001", "The session bus answers", layer=Layer.DBUS)
def session_bus(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the D-Bus session bus answers at all.

    Every portal request travels over it; without it nothing else on the portal side
    can work or even be checked, so the portal findings then follow from this one.
    """
    dbus = snapshot.dbus
    if dbus is None:
        return
    if dbus.reachable is True:
        yield Finding(
            id="SSD-DBUS-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="The session bus answers",
            reason="busctl --user reached the bus daemon.",
        )
    elif dbus.reachable is False:
        yield Finding(
            id="SSD-DBUS-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="The session bus does not answer",
            reason="busctl --user could not connect, so no portal can be reached.",
            evidence=(Evidence("busctl", "reachable", "false"),),
            recommended_action=(
                "Run the tool inside the desktop session; check that DBUS_SESSION_BUS_ADDRESS "
                "points to a running bus."
            ),
            verify_command="busctl --user status",
        )
    else:
        yield Finding(
            id="SSD-DBUS-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="The session bus was not checked",
            reason="busctl could not be run (see the probe failures).",
            limitations=("busctl comes with systemd; without it the bus is not inspected.",),
        )


@RULES.rule("SSD-PKG-001", "xdg-desktop-portal is installed", layer=Layer.PORTAL_FRONTEND)
def frontend_package(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the portal frontend package, which every portal request goes through, is "
    "installed."""
    packages = snapshot.packages
    if packages is None:
        return
    info = next((p for p in packages.packages if p.name == "xdg-desktop-portal"), None)
    evidence = (
        Evidence(
            packages.source or "packages", "xdg-desktop-portal", info.state.value if info else None
        ),
    )
    if info is not None and info.state is PackageState.INSTALLED:
        yield Finding(
            id="SSD-PKG-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH if packages.source != "files" else Confidence.MEDIUM,
            summary=f"xdg-desktop-portal {info.version or ''} is installed".replace("  ", " "),
            reason=f"Reported by {packages.source}.",
            evidence=evidence,
        )
    elif info is not None and info.state in (PackageState.NOT_INSTALLED, PackageState.BROKEN):
        yield Finding(
            id="SSD-PKG-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="xdg-desktop-portal is not (fully) installed",
            reason=(
                f"{packages.source} reports it as {info.state.value.replace('_', ' ')}; no portal "
                "request can work."
            ),
            evidence=evidence,
            recommended_action="Install the xdg-desktop-portal package with your package manager.",
        )
    else:
        yield Finding(
            id="SSD-PKG-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="Whether xdg-desktop-portal is installed is unknown",
            reason="No package manager answered and its program was not found.",
            evidence=evidence,
        )


@RULES.rule(
    "SSD-SERVICE-001",
    "The portal's user service is not failed or masked",
    layer=Layer.PORTAL_FRONTEND,
)
def frontend_unit(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether xdg-desktop-portal.service is usable for the user manager.

    A failed unit is restarted on the next request but usually fails the same way; a
    masked one can never start. Inactive is normal: portals start on demand.
    """
    services = snapshot.services
    if services is None or services.services is None:
        return
    unit = next((s for s in services.services if s.unit == "xdg-desktop-portal.service"), None)
    if unit is None or unit.load_state is None:
        return
    evidence = (
        Evidence("systemctl", "LoadState", unit.load_state),
        Evidence("systemctl", "ActiveState", unit.active_state),
    )
    verify = "systemctl --user status xdg-desktop-portal.service"
    if unit.load_state == "masked":
        yield Finding(
            id="SSD-SERVICE-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="xdg-desktop-portal.service is masked",
            reason="A masked unit can never start, so the portal is unavailable.",
            evidence=evidence,
            recommended_action="systemctl --user unmask xdg-desktop-portal.service",
            verify_command=verify,
        )
    elif unit.active_state == "failed":
        yield Finding(
            id="SSD-SERVICE-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="xdg-desktop-portal.service has failed",
            reason="Its last start failed; the next request will probably fail the same way.",
            evidence=evidence,
            recommended_action="Read why: journalctl --user -u xdg-desktop-portal.service -b",
            verify_command=verify,
        )
    elif unit.load_state == "not-found":
        yield Finding(
            id="SSD-SERVICE-001",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            summary="The user manager has no xdg-desktop-portal.service",
            reason=(
                "The portal can then only be started by D-Bus directly, outside the user manager."
            ),
            evidence=evidence,
            verify_command=verify,
        )
    else:
        yield Finding(
            id="SSD-SERVICE-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary=f"xdg-desktop-portal.service is {unit.active_state}",
            reason="Loaded and not failed; inactive is normal, it starts on demand.",
            evidence=evidence,
        )


@RULES.rule("SSD-PORTAL-001", "The portal frontend offers ScreenCast", layer=Layer.PORTAL_FRONTEND)
def frontend(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether org.freedesktop.portal.Desktop runs (or can start) and offers ScreenCast.

    The frontend exports org.freedesktop.portal.ScreenCast only when a backend
    implements it, so a running frontend without it means no backend was found. A
    frontend that is not running is fine if the bus can start it.
    """
    dbus = snapshot.dbus
    if dbus is None:
        return
    cause = _bus_cause(snapshot)
    if cause is not None:
        yield Finding(
            id="SSD-PORTAL-001",
            status=Status.UNKNOWN,
            severity=Severity.HIGH,
            confidence=Confidence.LOW,
            summary="The portal frontend was not checked",
            reason="The session bus did not answer.",
            caused_by=cause,
        )
        return
    name = next((n for n in dbus.names if n.name == FRONTEND), None)
    portal = next((o for o in dbus.objects if o.name == FRONTEND), None)
    evidence = (
        Evidence(
            "busctl",
            "running",
            None if name is None or name.running is None else str(name.running).lower(),
        ),
        Evidence(
            "busctl",
            "activatable",
            None if name is None or name.activatable is None else str(name.activatable).lower(),
        ),
    )
    if name is None or name.running is None:
        yield Finding(
            id="SSD-PORTAL-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="The portal frontend was not checked",
            reason="Its bus name could not be asked about.",
            evidence=evidence,
        )
        return
    if not name.running:
        if name.activatable:
            yield Finding(
                id="SSD-PORTAL-001",
                status=Status.PASS,
                severity=Severity.INFO,
                confidence=Confidence.MEDIUM,
                summary="The portal frontend starts on demand",
                reason="It is not running now, but the bus can start it when an app asks.",
                evidence=evidence,
                limitations=("Whether it offers ScreenCast is only known once it runs.",),
            )
        else:
            yield Finding(
                id="SSD-PORTAL-001",
                status=Status.FAIL,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                summary="The portal frontend cannot start",
                reason="org.freedesktop.portal.Desktop is neither running nor activatable.",
                evidence=evidence,
                recommended_action=(
                    "Install xdg-desktop-portal, or reinstall it if its D-Bus service file is "
                    "missing."
                ),
                verify_command="busctl --user list --activatable | grep portal.Desktop",
            )
        return
    if portal is None or portal.interfaces is None:
        yield Finding(
            id="SSD-PORTAL-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="The running portal frontend could not be introspected",
            reason="See the probe failures.",
            evidence=evidence,
        )
        return
    if SCREENCAST not in portal.interfaces:
        yield Finding(
            id="SSD-PORTAL-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="The portal frontend does not offer ScreenCast",
            reason=(
                "It runs, but exports no ScreenCast interface: it found no backend that "
                "implements it."
            ),
            evidence=evidence,
            recommended_action=(
                "See why no backend was chosen: screenshare-doctor routes explain ScreenCast"
            ),
            verify_command="screenshare-doctor check dbus",
        )
        return
    detail = ""
    if portal.screencast is not None and portal.screencast.version is not None:
        detail = f" (version {portal.screencast.version})"
    yield Finding(
        id="SSD-PORTAL-001",
        status=Status.PASS,
        severity=Severity.INFO,
        confidence=Confidence.HIGH,
        summary=f"The portal frontend offers ScreenCast{detail}",
        reason="org.freedesktop.portal.Desktop runs and exports org.freedesktop.portal.ScreenCast.",
        evidence=evidence,
    )


@RULES.rule(
    "SSD-PORTAL-002", "ScreenCast has a backend that can answer", layer=Layer.PORTAL_BACKEND
)
def backend(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Which backend the configuration selects for ScreenCast, and whether it can answer.

    The prediction follows the portal's own rules for its version; the bus then says
    whether that backend runs or can start and really implements ScreenCast.
    Configured is not the same as working, so both are needed for a pass.
    """
    route = screencast_route(snapshot)
    if route is None:
        return
    observation = observe_route(route, snapshot.dbus)
    explain = "screenshare-doctor routes explain ScreenCast"
    evidence = (
        Evidence("route", "backend", route.backend.source if route.backend else None),
        Evidence("route", "decided by", route.config or route.rule.value),
        Evidence("busctl", "agreement", observation.agreement.value),
    )
    limitations = route.uncertain
    stale = observation.agreement is Agreement.OFFERED_WITHOUT_BACKEND
    restart = "systemctl --user restart xdg-desktop-portal.service"
    stale_note = (
        " The running portal still offers ScreenCast: it reads its configuration only when "
        "it starts, so it was started before this changed and keeps the old choice until "
        "it is restarted."
    )
    if route.kind is RouteKind.DISABLED:
        action = (
            f"Remove the none entry from {route.config} "
            "if it was not meant to disable screen sharing."
        )
        yield Finding(
            id="SSD-PORTAL-002",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="ScreenCast is disabled by a portals.conf",
            reason=f"{route.config} sets it to none." + (stale_note if stale else ""),
            evidence=evidence,
            recommended_action=action
            + (f" Restart the portal afterwards: {restart}" if stale else ""),
            verify_command=explain,
            limitations=limitations,
        )
        return
    if route.backend is None:
        yield Finding(
            id="SSD-PORTAL-002",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="No installed backend implements ScreenCast",
            reason="No configuration entry or fallback leads to a backend with ScreenCast."
            + (stale_note if stale else ""),
            evidence=evidence,
            recommended_action=(
                "Install your desktop's portal backend (see screenshare-doctor check desktop)."
            ),
            verify_command=explain,
            limitations=limitations,
        )
        return
    source = route.backend.source
    agreement = observation.agreement
    if agreement in (Agreement.CONSISTENT, Agreement.STARTS_ON_DEMAND):
        how = "runs" if agreement is Agreement.CONSISTENT else "starts on demand"
        yield Finding(
            id="SSD-PORTAL-002",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH if not limitations else Confidence.MEDIUM,
            summary=f"ScreenCast goes to the {source} backend, which {how}",
            reason=f"Selected by {route.config or route.rule.value}.",
            evidence=evidence,
            limitations=limitations,
        )
    elif agreement in (Agreement.CANNOT_START, Agreement.MISSING_INTERFACE, Agreement.NOT_OFFERED):
        reasons = {
            Agreement.CANNOT_START: "it is neither running nor activatable on the bus",
            Agreement.MISSING_INTERFACE: "the running backend does not export ScreenCast",
            Agreement.NOT_OFFERED: "the running frontend does not offer ScreenCast",
        }
        yield Finding(
            id="SSD-PORTAL-002",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary=f"The selected {source} backend cannot answer",
            reason=f"The configuration selects {source}, but {reasons[agreement]}.",
            evidence=evidence,
            recommended_action=(
                f"Check that {route.backend.dbus_name} is installed and starts; see {explain}"
            ),
            verify_command="screenshare-doctor check dbus",
            limitations=limitations,
        )
    else:
        yield Finding(
            id="SSD-PORTAL-002",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary=f"ScreenCast is configured for {source}; not confirmed on the bus",
            reason=(
                "The prediction could not be checked: the bus did not answer, or the backend's "
                "name is not one this tool probes."
            ),
            evidence=evidence,
            caused_by=_bus_cause(snapshot),
            limitations=limitations,
        )


@RULES.rule(
    "SSD-PORTAL-003", "The portal reads the configuration as intended", layer=Layer.PORTAL_FRONTEND
)
def configuration(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether some portal file is silently ignored or could not be checked.

    The portal skips an unreadable portals.conf or .portal file without telling anyone,
    and a duplicate key keeps only its last value. Such files are the usual reason a
    configuration "does nothing".
    """
    files = snapshot.portal_files
    if files is None:
        return
    ignored = [f"{c.path}: {c.error}" for c in files.configs if not c.usable]
    ignored += [f"{d.path}: {d.error}" for d in files.descriptors if d.error is not None]
    duplicates = [
        f"{c.path}: {', '.join(c.duplicates)} set more than once"
        for c in files.configs
        if c.duplicates
    ]
    evidence = tuple(Evidence("portal file", "ignored", item) for item in dict.fromkeys(ignored))
    if ignored or duplicates:
        yield Finding(
            id="SSD-PORTAL-003",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            summary="The portal ignores part of its configuration",
            reason="; ".join(dict.fromkeys(ignored + duplicates)),
            evidence=evidence,
            recommended_action=(
                "Fix or remove the files listed; the portal does not report them itself."
            ),
            verify_command="screenshare-doctor routes explain ScreenCast",
        )
    elif files.unreadable:
        yield Finding(
            id="SSD-PORTAL-003",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="Some portal files could not be read",
            reason=", ".join(files.unreadable),
            evidence=tuple(
                Evidence("portal file", "unreadable", path) for path in files.unreadable
            ),
        )
    else:
        yield Finding(
            id="SSD-PORTAL-003",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="Every portal file found is read",
            reason=(
                f"{len(files.configs)} configuration file(s) and {len(files.descriptors)} "
                "descriptor(s), none ignored."
            ),
        )


@RULES.rule("SSD-PORTAL-004", "Single windows can be shared", layer=Layer.PORTAL_BACKEND)
def window_sharing(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the running frontend reports the window source type for ScreenCast.

    AvailableSourceTypes comes from the backend: without "window" an app can only
    offer whole screens, which looks like "the window I want is missing".
    """
    dbus = snapshot.dbus
    if dbus is None or dbus.reachable is not True:
        return
    portal = next((o for o in dbus.objects if o.name == FRONTEND), None)
    if portal is None or portal.screencast is None or portal.screencast.source_types is None:
        yield _window_sharing_unchecked(snapshot, portal)
        return
    sources = source_type_names(portal.screencast.source_types)
    evidence = (Evidence("busctl", "AvailableSourceTypes", str(portal.screencast.source_types)),)
    if "window" in sources:
        yield Finding(
            id="SSD-PORTAL-004",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary=f"ScreenCast offers {', '.join(sources)}",
            reason="The backend reports the window source type.",
            evidence=evidence,
        )
    else:
        yield Finding(
            id="SSD-PORTAL-004",
            status=Status.WARN,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            summary=f"ScreenCast offers only {', '.join(sources) or 'nothing'}",
            reason=(
                "The backend does not report the window source type, so apps cannot offer single "
                "windows."
            ),
            evidence=evidence,
            recommended_action=(
                "Share the whole screen, or use a backend that supports windows for your desktop."
            ),
        )


def _window_sharing_unchecked(snapshot: Snapshot, portal: PortalObject | None) -> Finding:
    """SSD-PORTAL-004 when the running frontend did not tell which sources it offers."""
    names = snapshot.dbus.names if snapshot.dbus else ()
    frontend = next((n for n in names if n.name == FRONTEND), None)
    if portal is None and (frontend is None or frontend.running is not True):
        return Finding(
            id="SSD-PORTAL-004",
            status=Status.NOT_TESTED,
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            summary="Window sharing was not checked: the portal is not running",
            reason=(
                "Which sources ScreenCast offers is only known from the running portal, and "
                "asking a portal that is not running would start it."
            ),
            recommended_action=(
                "Open the screen-sharing picker in any app once and cancel it; the portal then "
                "keeps running, and the check can read what it offers."
            ),
            verify_command="screenshare-doctor check dbus",
        )
    if portal is not None and portal.interfaces is not None and SCREENCAST not in portal.interfaces:
        return Finding(
            id="SSD-PORTAL-004",
            status=Status.NOT_TESTED,
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            summary="Window sharing was not checked: the portal offers no ScreenCast",
            reason="Without the ScreenCast interface there are no source types to read.",
            caused_by="SSD-PORTAL-001",
        )
    return Finding(
        id="SSD-PORTAL-004",
        status=Status.UNKNOWN,
        severity=Severity.MEDIUM,
        confidence=Confidence.LOW,
        summary="The portal did not say which sources ScreenCast offers",
        reason="Its AvailableSourceTypes property could not be read (see the probe failures).",
        verify_command="screenshare-doctor check dbus",
    )
