"""The desktop and compositor layers: how the setup compares with the desktop's defaults."""

from __future__ import annotations

from collections.abc import Iterator

from screenshare_doctor.bundles import DesktopBundle, bundle_for
from screenshare_doctor.bundles.check import Expectation, check_bundle
from screenshare_doctor.desktops import identify_desktop
from screenshare_doctor.models import (
    Confidence,
    Evidence,
    Finding,
    Layer,
    Severity,
    Snapshot,
    Status,
)
from screenshare_doctor.rules.catalog import RULES
from screenshare_doctor.rules.engine import RuleContext

_ORDER = (Status.FAIL, Status.WARN, Status.UNKNOWN)


def _bundle(snapshot: Snapshot) -> tuple[DesktopBundle | None, str | None]:
    """The bundle of the desktop the portal sees, and the desktop name it was found by."""
    services = snapshot.services
    env = services.activation_environment if services else None
    if env is None and snapshot.session is not None:
        env = snapshot.session.environment
    if env is None:
        return None, None
    identity = identify_desktop(env)
    return bundle_for(identity.family), identity.name


def _collected(snapshot: Snapshot) -> bool:
    return any(x is not None for x in (snapshot.packages, snapshot.portal_files, snapshot.dbus))


@RULES.rule(
    "SSD-DESKTOP-001", "The setup matches the desktop's defaults", layer=Layer.PORTAL_BACKEND
)
def desktop_defaults(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """How the portal setup compares with what the desktop ships by default.

    Checks the desktop's backend package, its .portal file, the desktop's portals.conf,
    the ScreenCast route and the backend on the bus (see docs/desktops.md for the
    defaults and their sources). A difference that may be deliberate, such as another
    backend, is a warning: the defaults are expectations, not verdicts.
    """
    if not _collected(snapshot):
        return
    bundle, name = _bundle(snapshot)
    if bundle is None:
        yield Finding(
            id="SSD-DESKTOP-001",
            status=Status.NOT_APPLICABLE,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary="No defaults known for this desktop",
            reason=(
                f"The desktop ({name or 'not named'}) is none of GNOME, KDE Plasma, Hyprland "
                "or a wlroots compositor."
            ),
            recommended_action=(
                "Compare with a known desktop: screenshare-doctor check desktop --as gnome"
            ),
        )
        return
    expectations = [e for e in check_bundle(bundle, snapshot) if e.key != "compositor"]
    status = next((s for s in _ORDER if any(e.status is s for e in expectations)), Status.PASS)
    evidence = tuple(
        Evidence(f"{bundle.name} default", e.summary, f"{e.detail} ({e.status.value})")
        for e in expectations
    )
    if status is Status.PASS:
        yield Finding(
            id="SSD-DESKTOP-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary=f"The setup matches {bundle.name}'s defaults",
            reason=f"All {len(expectations)} expectations hold.",
            evidence=evidence,
        )
        return
    problems = [e for e in expectations if e.status in _ORDER]
    severity = {Status.FAIL: Severity.HIGH, Status.WARN: Severity.MEDIUM}.get(status, Severity.LOW)
    yield Finding(
        id="SSD-DESKTOP-001",
        status=status,
        severity=severity,
        confidence=Confidence.HIGH if status is not Status.UNKNOWN else Confidence.LOW,
        summary=f"The setup differs from {bundle.name}'s defaults",
        reason="; ".join(_describe(e) for e in problems),
        evidence=evidence,
        recommended_action=_action(bundle, problems),
        verify_command="screenshare-doctor check desktop",
    )


def _describe(expectation: Expectation) -> str:
    return f"{expectation.summary} - {expectation.status.value} ({expectation.detail})"


def _action(bundle: DesktopBundle, problems: list[Expectation]) -> str | None:
    keys = {e.key for e in problems if e.status is Status.FAIL}
    if "backend_package" in keys or "backend_descriptor" in keys:
        return f"Install {bundle.backend_package} with your package manager."
    if "route" in keys:
        return "See why ScreenCast is not routed: screenshare-doctor routes explain ScreenCast"
    if any(e.key == "desktop_config" for e in problems) and bundle.config_shipped_by:
        return (
            f"{bundle.config_file} normally comes with {bundle.config_shipped_by}; "
            "reinstall it if you did not remove the file on purpose."
        )
    return None


@RULES.rule("SSD-COMPOSITOR-001", "The compositor offers screen casts", layer=Layer.COMPOSITOR)
def compositor(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the compositor service the desktop's backend captures from is running.

    On GNOME the backend asks Mutter over org.gnome.Mutter.ScreenCast; if gnome-shell
    does not provide it, there is nothing to capture from. KDE Plasma, Hyprland and the
    wlroots compositors offer screen casts through Wayland protocols, which this tool
    does not inspect.
    """
    if snapshot.dbus is None:
        return
    bundle, _ = _bundle(snapshot)
    if bundle is None:
        return
    expectation = next(e for e in check_bundle(bundle, snapshot) if e.key == "compositor")
    cause = "SSD-DBUS-001" if snapshot.dbus.reachable is not True else None
    severity = {Status.FAIL: Severity.HIGH}.get(expectation.status, Severity.INFO)
    yield Finding(
        id="SSD-COMPOSITOR-001",
        status=expectation.status,
        severity=severity,
        confidence=Confidence.HIGH if expectation.status is not Status.UNKNOWN else Confidence.LOW,
        summary=expectation.summary
        if expectation.status is not Status.FAIL
        else f"{bundle.compositor_bus_name} is not running",
        reason=expectation.detail,
        evidence=expectation.evidence,
        recommended_action=(
            (
                "Log out and in again; if it persists, check gnome-shell's log: journalctl "
                "--user -b | grep -i screencast"
            )
            if expectation.status is Status.FAIL
            else None
        ),
        caused_by=cause if expectation.status is Status.UNKNOWN else None,
    )
