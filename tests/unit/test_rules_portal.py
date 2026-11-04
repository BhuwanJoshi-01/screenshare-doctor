"""D-Bus and portal rules (SSD-DBUS-001, SSD-PKG-001, SSD-SERVICE-001, SSD-PORTAL-*)."""

from __future__ import annotations

import dataclasses

import pytest

from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    Finding,
    PackageFacts,
    PackageInfo,
    PackageState,
    PortalDescriptor,
    PortalObject,
    PortalsConf,
    ScreenCastProperties,
    ServiceFacts,
    Snapshot,
    Status,
    UserService,
)
from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.rules.engine import evaluate, root_causes
from tests.scenarios import gnome_snapshot

FRONTEND = "org.freedesktop.portal.Desktop"
GNOME = "org.freedesktop.impl.portal.desktop.gnome"
PORTAL_RULES = ("SSD-DBUS-", "SSD-PKG-", "SSD-SERVICE-", "SSD-PORTAL-")


@pytest.fixture(scope="module")
def real() -> Snapshot:
    return gnome_snapshot()


def _findings(snapshot: Snapshot) -> dict[str, Finding]:
    rules = [rule for rule in builtin_rules() if rule.id.startswith(PORTAL_RULES)]
    return {finding.id: finding for finding in evaluate(snapshot, rules)}


def test_real_gnome_machine_passes_every_portal_rule(real: Snapshot) -> None:
    findings = _findings(real)
    assert {key: f.status for key, f in findings.items()} == {
        "SSD-DBUS-001": Status.PASS,
        "SSD-PKG-001": Status.PASS,
        "SSD-SERVICE-001": Status.PASS,
        "SSD-PORTAL-001": Status.PASS,
        "SSD-PORTAL-002": Status.PASS,
        "SSD-PORTAL-003": Status.PASS,
        "SSD-PORTAL-004": Status.PASS,
    }
    assert findings["SSD-PKG-001"].summary == "xdg-desktop-portal 1.21.1+ds-1ubuntu3.1 is installed"
    assert findings["SSD-PORTAL-001"].summary == "The portal frontend offers ScreenCast (version 5)"
    assert findings["SSD-PORTAL-002"].summary == "ScreenCast goes to the gnome backend, which runs"
    assert findings["SSD-PORTAL-004"].summary == "ScreenCast offers monitor, window, virtual"


def test_unreachable_bus_is_one_root_cause() -> None:
    snapshot = dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=False))
    findings = evaluate(snapshot, [r for r in builtin_rules() if r.id.startswith(PORTAL_RULES)])
    by_id = {f.id: f for f in findings}
    assert by_id["SSD-DBUS-001"].status is Status.FAIL
    assert by_id["SSD-PORTAL-001"].caused_by == "SSD-DBUS-001"
    assert by_id["SSD-PORTAL-002"].caused_by == "SSD-DBUS-001"
    roots = {f.id for f in root_causes(findings)}
    assert "SSD-PORTAL-001" not in roots
    assert "SSD-DBUS-001" in roots


def test_busctl_missing_is_unknown() -> None:
    snapshot = dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=None))
    assert _findings(snapshot)["SSD-DBUS-001"].status is Status.UNKNOWN


def test_frontend_package_missing(real: Snapshot) -> None:
    packages = PackageFacts(
        "dpkg", (PackageInfo("xdg-desktop-portal", PackageState.NOT_INSTALLED),)
    )
    finding = _findings(dataclasses.replace(real, packages=packages))["SSD-PKG-001"]
    assert finding.status is Status.FAIL


def test_frontend_package_unknown_without_a_package_manager(real: Snapshot) -> None:
    packages = PackageFacts("files", (PackageInfo("xdg-desktop-portal", PackageState.UNKNOWN),))
    assert (
        _findings(dataclasses.replace(real, packages=packages))["SSD-PKG-001"].status
        is Status.UNKNOWN
    )


@pytest.mark.parametrize(
    ("load", "active", "status"),
    [
        ("masked", "inactive", Status.FAIL),
        ("loaded", "failed", Status.FAIL),
        ("not-found", "inactive", Status.WARN),
        ("loaded", "inactive", Status.PASS),
    ],
)
def test_frontend_unit_states(real: Snapshot, load: str, active: str, status: Status) -> None:
    services = ServiceFacts(
        services=(UserService("xdg-desktop-portal.service", load, active, None, "static"),)
    )
    assert (
        _findings(dataclasses.replace(real, services=services))["SSD-SERVICE-001"].status is status
    )


def _dbus(*names: BusName, objects: tuple[PortalObject, ...] = ()) -> DbusFacts:
    return DbusFacts(reachable=True, names=names, objects=objects)


def test_frontend_that_starts_on_demand(real: Snapshot) -> None:
    dbus = _dbus(BusName(FRONTEND, running=False, activatable=True))
    assert _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-001"].status is Status.PASS


def test_frontend_that_cannot_start(real: Snapshot) -> None:
    dbus = _dbus(BusName(FRONTEND, running=False, activatable=False))
    assert _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-001"].status is Status.FAIL


def test_frontend_without_screencast(real: Snapshot) -> None:
    dbus = _dbus(
        BusName(FRONTEND, True, True),
        objects=(PortalObject(FRONTEND, ("org.freedesktop.portal.FileChooser",)),),
    )
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-001"]
    assert finding.status is Status.FAIL
    assert "found no backend" in finding.reason


def test_screencast_disabled_by_the_user(real: Snapshot) -> None:
    user_file = "/home/user/.config/xdg-desktop-portal/gnome-portals.conf"
    snapshot = gnome_snapshot(
        {user_file: b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"}
    )
    finding = _findings(snapshot)["SSD-PORTAL-002"]
    assert finding.status is Status.FAIL
    assert "disabled" in finding.summary


def test_selected_backend_that_cannot_start(real: Snapshot) -> None:
    dbus = _dbus(BusName(FRONTEND, True, True), BusName(GNOME, running=False, activatable=False))
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-002"]
    assert finding.status is Status.FAIL
    assert "neither running nor activatable" in finding.reason


def test_no_backend_at_all(real: Snapshot) -> None:
    assert real.portal_files is not None
    files = dataclasses.replace(real.portal_files, descriptors=())
    assert (
        _findings(dataclasses.replace(real, portal_files=files))["SSD-PORTAL-002"].status
        is Status.FAIL
    )


def test_ignored_user_config_warns() -> None:
    snapshot = gnome_snapshot(
        {"/home/user/.config/xdg-desktop-portal/portals.conf": b"default=kde\n"}
    )
    finding = _findings(snapshot)["SSD-PORTAL-003"]
    assert finding.status is Status.WARN
    assert "key before the first group" in finding.reason


def test_broken_descriptor_and_duplicates_warn(real: Snapshot) -> None:
    assert real.portal_files is not None
    files = dataclasses.replace(
        real.portal_files,
        descriptors=(
            *real.portal_files.descriptors,
            PortalDescriptor(
                "x",
                "/usr/share/xdg-desktop-portal/portals/x.portal",
                error="no DBusName in [portal]",
            ),
        ),
        configs=(
            PortalsConf(
                "/etc/xdg/xdg-desktop-portal/portals.conf",
                (("default", ("gnome",)),),
                duplicates=("default",),
            ),
        ),
    )
    finding = _findings(dataclasses.replace(real, portal_files=files))["SSD-PORTAL-003"]
    assert finding.status is Status.WARN
    assert "no DBusName" in finding.reason
    assert "default set more than once" in finding.reason


def test_unreadable_files_are_unknown(real: Snapshot) -> None:
    assert real.portal_files is not None
    files = dataclasses.replace(
        real.portal_files, unreadable=("/etc/xdg-desktop-portal/portals.conf",)
    )
    assert (
        _findings(dataclasses.replace(real, portal_files=files))["SSD-PORTAL-003"].status
        is Status.UNKNOWN
    )


def test_monitor_only_backend_warns(real: Snapshot) -> None:
    dbus = _dbus(
        BusName(FRONTEND, True, True),
        objects=(
            PortalObject(
                FRONTEND,
                ("org.freedesktop.portal.ScreenCast",),
                ScreenCastProperties(version=4, source_types=1, cursor_modes=3),
            ),
        ),
    )
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-004"]
    assert finding.status is Status.WARN
    assert finding.summary == "ScreenCast offers only monitor"


def test_portal_rules_stay_silent_without_facts() -> None:
    assert _findings(Snapshot(tool_version="0.1.0", created_at="x")) == {}


def test_a_portal_running_on_its_old_configuration_is_explained() -> None:
    # The replayed bus still offers ScreenCast, as a portal started before the edit would.
    user_file = "/home/user/.config/xdg-desktop-portal/gnome-portals.conf"
    snapshot = gnome_snapshot(
        {user_file: b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"}
    )
    finding = _findings(snapshot)["SSD-PORTAL-002"]
    assert "reads its configuration only when it starts" in finding.reason
    assert finding.recommended_action is not None
    assert "systemctl --user restart xdg-desktop-portal.service" in finding.recommended_action


def test_no_restart_advice_when_the_portal_agrees(real: Snapshot) -> None:
    dbus = _dbus(BusName(FRONTEND, True, True), objects=(PortalObject(FRONTEND, ()),))
    assert real.portal_files is not None
    files = dataclasses.replace(real.portal_files, descriptors=())
    finding = _findings(dataclasses.replace(real, portal_files=files, dbus=dbus))["SSD-PORTAL-002"]
    assert "restart" not in (finding.recommended_action or "")


# Hyprland 0.57 on Arch: the portal starts on demand and was not running during doctor.
# The check that matters most for "the window I want is missing" must not vanish then.
@pytest.mark.xfail(strict=True, reason="WLD-010")
def test_window_sharing_not_tested_while_the_portal_is_stopped(real: Snapshot) -> None:
    dbus = _dbus(BusName(FRONTEND, running=False, activatable=True))
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-004"]
    assert finding.status is Status.NOT_TESTED
    assert finding.summary == "Window sharing was not checked: the portal is not running"
    assert finding.verify_command == "screenshare-doctor check dbus"


@pytest.mark.xfail(strict=True, reason="WLD-010")
def test_window_sharing_follows_a_frontend_without_screencast(real: Snapshot) -> None:
    dbus = _dbus(
        BusName(FRONTEND, True, True),
        objects=(PortalObject(FRONTEND, ("org.freedesktop.portal.FileChooser",)),),
    )
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-004"]
    assert finding.status is Status.NOT_TESTED
    assert finding.caused_by == "SSD-PORTAL-001"


@pytest.mark.xfail(strict=True, reason="WLD-010")
def test_window_sharing_unknown_without_the_property(real: Snapshot) -> None:
    dbus = _dbus(
        BusName(FRONTEND, True, True),
        objects=(PortalObject(FRONTEND, ("org.freedesktop.portal.ScreenCast",)),),
    )
    finding = _findings(dataclasses.replace(real, dbus=dbus))["SSD-PORTAL-004"]
    assert finding.status is Status.UNKNOWN
