"""Compare a desktop bundle with what the snapshot found.

Each expectation is answered from facts only: ``pass`` when they match, ``fail`` when
they show the expectation cannot hold (the backend is not installed, cannot be
started…), ``warn`` when the setup differs but may still work (another backend was
chosen on purpose), ``unknown`` when the facts are missing. Pure function of the
snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

from screenshare_doctor.bundles import DesktopBundle
from screenshare_doctor.models import Evidence, PackageState, Snapshot, Status
from screenshare_doctor.routes import (
    PortalBehaviour,
    RouteKind,
    parse_portal_version,
    resolve_route,
)

SCREENCAST = "org.freedesktop.impl.portal.ScreenCast"


@dataclass(frozen=True, slots=True)
class Expectation:
    """One expectation of a bundle and how the snapshot answers it."""

    key: str
    summary: str
    status: Status
    detail: str
    evidence: tuple[Evidence, ...] = ()


def _portal_version(snapshot: Snapshot) -> str | None:
    for package in snapshot.packages.packages if snapshot.packages else ():
        if package.name == "xdg-desktop-portal" and package.state is PackageState.INSTALLED:
            return package.version
    return None


def check_bundle(bundle: DesktopBundle, snapshot: Snapshot) -> tuple[Expectation, ...]:
    return (
        _package(bundle, snapshot),
        _descriptor(bundle, snapshot),
        _config(bundle, snapshot),
        _route(bundle, snapshot),
        _on_bus(bundle, snapshot),
        _compositor(bundle, snapshot),
    )


def _package(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    summary = f"{bundle.backend_package} is installed"
    packages = snapshot.packages
    info = (
        next((p for p in packages.packages if p.name == bundle.backend_package), None)
        if packages
        else None
    )
    if info is None or info.state is PackageState.UNKNOWN:
        return Expectation(
            "backend_package", summary, Status.UNKNOWN, "the package state could not be read"
        )
    evidence = (
        (Evidence(packages.source or "packages", bundle.backend_package, info.state.value),)
        if packages
        else ()
    )
    if info.state is PackageState.INSTALLED:
        return Expectation(
            "backend_package",
            summary,
            Status.PASS,
            f"version {info.version or 'unknown'}",
            evidence,
        )
    if info.state is PackageState.BROKEN:
        return Expectation(
            "backend_package",
            summary,
            Status.FAIL,
            "the package is only partly installed",
            evidence,
        )
    return Expectation(
        "backend_package", summary, Status.FAIL, "the package is not installed", evidence
    )


def _descriptor(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    summary = f"{bundle.backend}.portal declares ScreenCast"
    files = snapshot.portal_files
    if files is None:
        return Expectation(
            "backend_descriptor", summary, Status.UNKNOWN, "the portal files were not read"
        )
    found = [d for d in files.descriptors if d.source == bundle.backend]
    if not found:
        return Expectation(
            "backend_descriptor",
            summary,
            Status.FAIL,
            f"no {bundle.backend}.portal in the portal directories",
        )
    descriptor = found[0]
    evidence = (Evidence("portal file", "path", descriptor.path),)
    if descriptor.error is not None:
        return Expectation(
            "backend_descriptor",
            summary,
            Status.FAIL,
            f"the portal ignores it: {descriptor.error}",
            evidence,
        )
    if SCREENCAST not in descriptor.interfaces:
        return Expectation(
            "backend_descriptor", summary, Status.FAIL, "it does not list ScreenCast", evidence
        )
    return Expectation("backend_descriptor", summary, Status.PASS, descriptor.path, evidence)


def _config(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    if bundle.config_file is None:
        return Expectation(
            "desktop_config",
            "the desktop installs a portals.conf",
            Status.NOT_APPLICABLE,
            f"{bundle.name} installs no portals.conf; "
            "the deprecated UseIn key or your own file decides",
        )
    summary = f"{bundle.config_file} is installed"
    files = snapshot.portal_files
    if files is None:
        return Expectation(
            "desktop_config", summary, Status.UNKNOWN, "the portal files were not read"
        )
    matches = [c for c in files.configs if c.path.endswith(f"/{bundle.config_file}")]
    if not matches:
        return Expectation(
            "desktop_config",
            summary,
            Status.WARN,
            f"not found in any search directory; {bundle.config_shipped_by} installs it",
        )
    conf = matches[0]
    evidence = (Evidence("portal file", "path", conf.path),)
    if not conf.usable:
        return Expectation(
            "desktop_config", summary, Status.WARN, f"the portal ignores it: {conf.error}", evidence
        )
    return Expectation("desktop_config", summary, Status.PASS, conf.path, evidence)


def _route(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    summary = f"ScreenCast is routed to the {bundle.backend} backend"
    files = snapshot.portal_files
    if files is None:
        return Expectation("route", summary, Status.UNKNOWN, "the portal files were not read")
    route = resolve_route(
        SCREENCAST, files, PortalBehaviour(parse_portal_version(_portal_version(snapshot)))
    )
    if route.kind is RouteKind.DISABLED:
        return Expectation(
            "route", summary, Status.FAIL, f"ScreenCast is disabled by {route.config}"
        )
    if route.backend is None:
        return Expectation("route", summary, Status.FAIL, "no backend is selected for ScreenCast")
    evidence = (Evidence("route", "backend", route.backend.source),)
    if route.backend.source == bundle.backend:
        return Expectation(
            "route",
            summary,
            Status.PASS,
            f"decided by {route.config or route.rule.value}",
            evidence,
        )
    return Expectation(
        "route",
        summary,
        Status.WARN,
        f"routed to {route.backend.source} instead; fine if you chose it, "
        f"otherwise check {route.config or 'the fallbacks'}",
        evidence,
    )


def _on_bus(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    summary = f"{bundle.backend_bus_name} runs or can be started"
    dbus = snapshot.dbus
    name = (
        next((n for n in dbus.names if n.name == bundle.backend_bus_name), None) if dbus else None
    )
    if name is None or (name.running is None and name.activatable is None):
        return Expectation(
            "backend_on_bus", summary, Status.UNKNOWN, "the session bus was not asked"
        )
    evidence = (
        Evidence(
            "busctl", "running", str(name.running).lower() if name.running is not None else None
        ),
        Evidence(
            "busctl",
            "activatable",
            str(name.activatable).lower() if name.activatable is not None else None,
        ),
    )
    if name.running:
        return Expectation("backend_on_bus", summary, Status.PASS, "running", evidence)
    if name.activatable:
        return Expectation(
            "backend_on_bus", summary, Status.PASS, "not running; starts on demand", evidence
        )
    if name.running is False and name.activatable is False:
        return Expectation(
            "backend_on_bus", summary, Status.FAIL, "neither running nor activatable", evidence
        )
    return Expectation("backend_on_bus", summary, Status.UNKNOWN, "partly unknown", evidence)


def _compositor(bundle: DesktopBundle, snapshot: Snapshot) -> Expectation:
    if bundle.compositor_bus_name is None:
        return Expectation(
            "compositor",
            "the compositor offers screen casts",
            Status.NOT_APPLICABLE,
            f"{bundle.name} offers them through Wayland protocols, "
            "which this tool does not inspect",
        )
    summary = f"{bundle.compositor_bus_name} is running"
    dbus = snapshot.dbus
    name = (
        next((n for n in dbus.names if n.name == bundle.compositor_bus_name), None)
        if dbus
        else None
    )
    if name is None or name.running is None:
        return Expectation("compositor", summary, Status.UNKNOWN, "the session bus was not asked")
    evidence = (Evidence("busctl", bundle.compositor_bus_name, str(name.running).lower()),)
    if name.running:
        return Expectation("compositor", summary, Status.PASS, "running", evidence)
    return Expectation(
        "compositor",
        summary,
        Status.FAIL,
        "not running: the backend has nothing to capture from",
        evidence,
    )
