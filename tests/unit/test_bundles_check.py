"""Desktop expectations against the facts (WLD-007)."""

from __future__ import annotations

import dataclasses
import os
import stat

import pytest

from screenshare_doctor.bundles import DesktopBundle, load_bundles
from screenshare_doctor.bundles.check import check_bundle
from screenshare_doctor.desktops import DesktopFamily
from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    PackageFacts,
    PackageInfo,
    PackageState,
    PortalDescriptor,
    PortalsConf,
    Snapshot,
    Status,
)
from screenshare_doctor.orchestrator import inspect_routes
from tests.fakes import FakeRunner, read_env_fixture
from tests.scenarios import gnome_file_access, script_gnome_machine

BUNDLES = load_bundles()
GNOME = BUNDLES[DesktopFamily.GNOME]
KDE = BUNDLES[DesktopFamily.KDE]
HYPRLAND = BUNDLES[DesktopFamily.HYPRLAND]
WLROOTS = BUNDLES[DesktopFamily.WLROOTS]


@pytest.fixture(scope="module")
def real() -> Snapshot:
    runner = FakeRunner()
    script_gnome_machine(runner, uid=1000)
    read, list_dir = gnome_file_access()
    return inspect_routes(
        runner,
        environ=read_env_fixture("gnome-wayland-ubuntu"),
        uid=1000,
        stat=lambda path: os.stat_result((stat.S_IFSOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        which=lambda name: "/usr/bin/dpkg-query" if name == "dpkg-query" else None,
        exists=lambda path: path == "/var/lib/dpkg/status",
        read=read,
        list_dir=list_dir,
    )


def _statuses(snapshot: Snapshot, bundle: DesktopBundle) -> dict[str, Status]:
    return {e.key: e.status for e in check_bundle(bundle, snapshot)}


def test_real_gnome_machine_meets_every_gnome_expectation(real: Snapshot) -> None:
    expectations = check_bundle(GNOME, real)
    assert {e.key: e.status for e in expectations} == {
        "backend_package": Status.PASS,
        "backend_descriptor": Status.PASS,
        "desktop_config": Status.PASS,
        "route": Status.PASS,
        "backend_on_bus": Status.PASS,
        "compositor": Status.PASS,
    }
    route = next(e for e in expectations if e.key == "route")
    assert "gnome-portals.conf" in route.detail


def test_the_same_machine_judged_as_kde(real: Snapshot) -> None:
    statuses = _statuses(real, KDE)
    assert statuses["backend_package"] is Status.FAIL
    assert statuses["backend_descriptor"] is Status.FAIL
    assert statuses["desktop_config"] is Status.WARN  # plasma-workspace installs it
    assert statuses["route"] is Status.WARN  # gnome is chosen: another valid backend
    assert statuses["backend_on_bus"] is Status.FAIL
    assert statuses["compositor"] is Status.NOT_APPLICABLE


def test_desktop_config_warning_names_the_package(real: Snapshot) -> None:
    config = next(e for e in check_bundle(HYPRLAND, real) if e.key == "desktop_config")
    assert config.status is Status.WARN
    assert "hyprland installs it" in config.detail


def test_wlroots_ships_no_config(real: Snapshot) -> None:
    assert _statuses(real, WLROOTS)["desktop_config"] is Status.NOT_APPLICABLE


def test_nothing_collected_is_unknown_not_pass() -> None:
    statuses = _statuses(Snapshot(tool_version="0.1.0", created_at="x"), GNOME)
    assert set(statuses.values()) == {Status.UNKNOWN}


def test_broken_package(real: Snapshot) -> None:
    packages = PackageFacts(
        "dpkg", (PackageInfo("xdg-desktop-portal-gnome", PackageState.BROKEN, "50.0-1"),)
    )
    statuses = _statuses(dataclasses.replace(real, packages=packages), GNOME)
    assert statuses["backend_package"] is Status.FAIL


def test_descriptor_the_portal_ignores(real: Snapshot) -> None:
    assert real.portal_files is not None
    broken = PortalDescriptor(
        "gnome",
        "/usr/share/xdg-desktop-portal/portals/gnome.portal",
        error="no DBusName in [portal]",
    )
    files = dataclasses.replace(real.portal_files, descriptors=(broken,))
    expectations = {
        e.key: e for e in check_bundle(GNOME, dataclasses.replace(real, portal_files=files))
    }
    assert expectations["backend_descriptor"].status is Status.FAIL
    assert "no DBusName" in expectations["backend_descriptor"].detail
    assert expectations["route"].status is Status.FAIL


def test_config_the_portal_ignores(real: Snapshot) -> None:
    assert real.portal_files is not None
    bad = PortalsConf(
        "/usr/share/xdg-desktop-portal/gnome-portals.conf",
        usable=False,
        error="no [preferred] group",
    )
    files = dataclasses.replace(real.portal_files, configs=(bad,))
    config = next(
        e
        for e in check_bundle(GNOME, dataclasses.replace(real, portal_files=files))
        if e.key == "desktop_config"
    )
    assert config.status is Status.WARN
    assert "no [preferred] group" in config.detail


def test_screencast_disabled(real: Snapshot) -> None:
    assert real.portal_files is not None
    off = PortalsConf(
        "/home/user/.config/xdg-desktop-portal/portals.conf",
        (("org.freedesktop.impl.portal.ScreenCast", ("none",)),),
    )
    files = dataclasses.replace(real.portal_files, configs=(off, *real.portal_files.configs))
    route = next(
        e
        for e in check_bundle(GNOME, dataclasses.replace(real, portal_files=files))
        if e.key == "route"
    )
    assert route.status is Status.FAIL
    assert "disabled" in route.detail


def test_backend_that_starts_on_demand_passes() -> None:
    dbus = DbusFacts(True, (BusName("org.freedesktop.impl.portal.desktop.gnome", False, True),))
    on_bus = next(
        e
        for e in check_bundle(GNOME, Snapshot(tool_version="0", created_at="x", dbus=dbus))
        if e.key == "backend_on_bus"
    )
    assert (on_bus.status, on_bus.detail) == (Status.PASS, "not running; starts on demand")


def test_mutter_not_running() -> None:
    dbus = DbusFacts(True, (BusName("org.gnome.Mutter.ScreenCast", False, False),))
    compositor = next(
        e
        for e in check_bundle(GNOME, Snapshot(tool_version="0", created_at="x", dbus=dbus))
        if e.key == "compositor"
    )
    assert compositor.status is Status.FAIL
