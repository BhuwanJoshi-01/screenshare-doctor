"""Desktop, compositor, PipeWire and WirePlumber rules."""

from __future__ import annotations

import dataclasses

import pytest

from screenshare_doctor.collectors.pipewire import collect_pipewire
from screenshare_doctor.models import (
    BusName,
    DbusFacts,
    FailureKind,
    Finding,
    PackageFacts,
    PackageInfo,
    PackageState,
    PipeWireFacts,
    PortalDescriptor,
    PortalsConf,
    ProbeFailure,
    ServiceFacts,
    SessionEnvironment,
    Snapshot,
    Status,
    UserService,
)
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.rules.engine import evaluate
from tests.fakes import FakeRunner
from tests.scenarios import gnome_snapshot, script_gnome_pipewire

STACK_RULES = ("SSD-DESKTOP-", "SSD-COMPOSITOR-", "SSD-PW-", "SSD-WP-")


@pytest.fixture(scope="module")
def real() -> Snapshot:
    snapshot = gnome_snapshot()
    runner = FakeRunner()
    script_gnome_pipewire(runner)
    pipewire, _ = collect_pipewire(runner, snapshot.services)
    return dataclasses.replace(snapshot, pipewire=pipewire)


def _findings(snapshot: Snapshot) -> dict[str, Finding]:
    rules = [rule for rule in builtin_rules() if rule.id.startswith(STACK_RULES)]
    return {finding.id: finding for finding in evaluate(snapshot, rules)}


def _units(*units: tuple[str, str, str]) -> ServiceFacts:
    """``("pipewire.service", "loaded", "inactive")``-style unit states."""
    return ServiceFacts(
        services=tuple(UserService(name, load, active) for name, load, active in units),
        activation_environment=SessionEnvironment(
            current_desktop="ubuntu:GNOME", wayland_display="wayland-0"
        ),
    )


def test_real_gnome_machine_passes(real: Snapshot) -> None:
    findings = _findings(real)
    assert {key: f.status for key, f in findings.items()} == {
        "SSD-DESKTOP-001": Status.PASS,
        "SSD-COMPOSITOR-001": Status.PASS,
        "SSD-PW-001": Status.PASS,
        "SSD-WP-001": Status.PASS,
    }
    assert findings["SSD-DESKTOP-001"].summary == "The setup matches GNOME's defaults"
    assert findings["SSD-PW-001"].summary == "PipeWire 1.6.2 answers"


def test_missing_backend_package_fails_with_the_install_action(real: Snapshot) -> None:
    packages = PackageFacts(
        "dpkg", (PackageInfo("xdg-desktop-portal-gnome", PackageState.NOT_INSTALLED),)
    )
    finding = _findings(dataclasses.replace(real, packages=packages))["SSD-DESKTOP-001"]
    assert finding.status is Status.FAIL
    assert (
        finding.recommended_action == "Install xdg-desktop-portal-gnome with your package manager."
    )


def test_a_listed_but_missing_backend_keeps_the_defaults(real: Snapshot) -> None:
    user_file = "/home/user/.config/xdg-desktop-portal/portals.conf"
    conf = b"[preferred]\ndefault=gtk\norg.freedesktop.impl.portal.ScreenCast=wlr;gnome\n"
    # wlr is not installed, so gnome is still chosen: the defaults still hold.
    assert _findings(gnome_snapshot({user_file: conf}))["SSD-DESKTOP-001"].status is Status.PASS


def test_another_installed_backend_only_warns(real: Snapshot) -> None:
    assert real.portal_files is not None
    wlr = PortalDescriptor(
        "wlr",
        "/usr/share/xdg-desktop-portal/portals/wlr.portal",
        "org.freedesktop.impl.portal.desktop.wlr",
        ("org.freedesktop.impl.portal.ScreenCast",),
    )
    choice = PortalsConf(
        "/home/user/.config/xdg-desktop-portal/portals.conf",
        (("org.freedesktop.impl.portal.ScreenCast", ("wlr",)),),
    )
    files = dataclasses.replace(
        real.portal_files,
        descriptors=(*real.portal_files.descriptors, wlr),
        configs=(choice, *real.portal_files.configs),
    )
    finding = _findings(dataclasses.replace(real, portal_files=files))["SSD-DESKTOP-001"]
    assert finding.status is Status.WARN
    assert "routed to wlr instead" in finding.reason


def test_unknown_desktop_has_no_defaults(real: Snapshot) -> None:
    assert real.services is not None
    services = dataclasses.replace(
        real.services, activation_environment=SessionEnvironment(current_desktop="MyDesktop")
    )
    finding = _findings(dataclasses.replace(real, services=services))["SSD-DESKTOP-001"]
    assert finding.status is Status.NOT_APPLICABLE
    assert "MyDesktop" not in finding.reason  # only recognised names are quoted
    assert "SSD-COMPOSITOR-001" not in _findings(dataclasses.replace(real, services=services))


def test_mutter_not_running_fails(real: Snapshot) -> None:
    assert real.dbus is not None
    names = tuple(
        dataclasses.replace(n, running=False) if n.name == "org.gnome.Mutter.ScreenCast" else n
        for n in real.dbus.names
    )
    finding = _findings(
        dataclasses.replace(real, dbus=dataclasses.replace(real.dbus, names=names))
    )["SSD-COMPOSITOR-001"]
    assert finding.status is Status.FAIL
    assert finding.summary == "org.gnome.Mutter.ScreenCast is not running"


def test_compositor_follows_from_an_unreachable_bus(real: Snapshot) -> None:
    finding = _findings(dataclasses.replace(real, dbus=DbusFacts(reachable=False)))[
        "SSD-COMPOSITOR-001"
    ]
    assert (finding.status, finding.caused_by) == (Status.UNKNOWN, "SSD-DBUS-001")


def test_compositor_not_applicable_on_kde(real: Snapshot) -> None:
    assert real.services is not None
    services = dataclasses.replace(
        real.services, activation_environment=SessionEnvironment(current_desktop="KDE")
    )
    assert (
        _findings(dataclasses.replace(real, services=services))["SSD-COMPOSITOR-001"].status
        is Status.NOT_APPLICABLE
    )


def _pipewire_case(
    pipewire: PipeWireFacts,
    services: ServiceFacts,
    packages: PackageFacts | None = None,
    failures: tuple[ProbeFailure, ...] = (),
) -> dict[str, Finding]:
    return _findings(
        Snapshot(
            tool_version="0",
            created_at="x",
            pipewire=pipewire,
            services=services,
            packages=packages,
            probe_failures=failures,
        )
    )


SKIPPED = PipeWireFacts(
    skipped="pipewire.service is not running (inactive); connecting would start it"
)


def test_pipewire_on_demand_through_its_socket() -> None:
    findings = _pipewire_case(
        SKIPPED,
        _units(("pipewire.service", "loaded", "inactive"), ("pipewire.socket", "loaded", "active")),
    )
    assert findings["SSD-PW-001"].status is Status.PASS
    assert findings["SSD-PW-001"].summary == "PipeWire starts on demand"


def test_pipewire_that_cannot_start() -> None:
    findings = _pipewire_case(
        SKIPPED,
        _units(
            ("pipewire.service", "loaded", "inactive"), ("pipewire.socket", "loaded", "inactive")
        ),
    )
    assert findings["SSD-PW-001"].status is Status.FAIL


def test_pipewire_failed() -> None:
    findings = _pipewire_case(
        SKIPPED,
        _units(("pipewire.service", "loaded", "failed"), ("pipewire.socket", "loaded", "inactive")),
    )
    assert findings["SSD-PW-001"].summary == "pipewire.service has failed"


def test_pipewire_not_installed() -> None:
    packages = PackageFacts("dpkg", (PackageInfo("pipewire", PackageState.NOT_INSTALLED),))
    findings = _pipewire_case(SKIPPED, _units(), packages)
    assert findings["SSD-PW-001"].summary == "PipeWire is not installed"


def test_pipewire_running_but_silent() -> None:
    findings = _pipewire_case(PipeWireFacts(), _units(("pipewire.service", "loaded", "active")))
    assert findings["SSD-PW-001"].status is Status.FAIL


def test_pipewire_running_without_pw_dump_is_unknown() -> None:
    # Fedora 45 KDE: pw-dump is in pipewire-utils, which a minimal install leaves out.
    # A missing tool says nothing about the daemon, so this must not fail.
    failure = ProbeFailure("pw-dump", FailureKind.NOT_FOUND, "pw-dump was not found")
    findings = _pipewire_case(
        PipeWireFacts(), _units(("pipewire.service", "loaded", "active")), failures=(failure,)
    )
    finding = findings["SSD-PW-001"]
    assert finding.status is Status.UNKNOWN
    assert finding.summary == "PipeWire runs, but pw-dump is not installed to ask it"
    assert finding.recommended_action is not None
    assert "pipewire-utils" in finding.recommended_action


@pytest.mark.parametrize("kind", [FailureKind.PERMISSION_DENIED, FailureKind.MALFORMED_OUTPUT])
def test_pipewire_with_an_unusable_pw_dump_is_unknown(kind: FailureKind) -> None:
    failure = ProbeFailure("pw-dump", kind, "detail")
    findings = _pipewire_case(
        PipeWireFacts(), _units(("pipewire.service", "loaded", "active")), failures=(failure,)
    )
    assert findings["SSD-PW-001"].status is Status.UNKNOWN


def test_pipewire_that_times_out_still_fails() -> None:
    failure = ProbeFailure("pw-dump", FailureKind.TIMEOUT, "timed out after 5 s")
    findings = _pipewire_case(
        PipeWireFacts(), _units(("pipewire.service", "loaded", "active")), failures=(failure,)
    )
    assert findings["SSD-PW-001"].status is Status.FAIL


def test_pipewire_state_unknown() -> None:
    findings = _pipewire_case(
        PipeWireFacts(skipped="the state of pipewire.service is unknown"), ServiceFacts()
    )
    assert findings["SSD-PW-001"].status is Status.UNKNOWN


def test_wireplumber_missing_from_the_client_list() -> None:
    pipewire = PipeWireFacts(
        version="1.6.2",
        clients=("xdg-desktop-portal",),
        other_clients=0,
        camera_sources=0,
        other_video_sources=0,
        video_streams=0,
    )
    finding = _pipewire_case(pipewire, _units(("wireplumber.service", "loaded", "inactive")))[
        "SSD-WP-001"
    ]
    assert finding.status is Status.WARN


@pytest.mark.parametrize(("load", "active"), [("masked", "inactive"), ("loaded", "failed")])
def test_wireplumber_unit_broken(load: str, active: str) -> None:
    finding = _pipewire_case(SKIPPED, _units(("wireplumber.service", load, active)))["SSD-WP-001"]
    assert finding.status is Status.FAIL


def test_wireplumber_from_its_unit_when_pipewire_was_not_asked() -> None:
    finding = _pipewire_case(SKIPPED, _units(("wireplumber.service", "loaded", "active")))[
        "SSD-WP-001"
    ]
    assert (finding.status, finding.confidence.value) == (Status.PASS, "medium")


def test_stack_rules_stay_silent_without_facts() -> None:
    assert _findings(Snapshot(tool_version="0", created_at="x")) == {}


def test_bus_names_are_not_mistaken_for_missing(real: Snapshot) -> None:
    # A desktop backend that only starts on demand keeps the defaults intact.
    assert real.dbus is not None
    names = tuple(
        BusName(n.name, running=False, activatable=True) if n.name.endswith(".desktop.gnome") else n
        for n in real.dbus.names
    )
    finding = _findings(
        dataclasses.replace(real, dbus=dataclasses.replace(real.dbus, names=names))
    )["SSD-DESKTOP-001"]
    assert finding.status is Status.PASS


def test_desktop_evidence_survives_redaction(real: Snapshot) -> None:
    """Evidence like "pass: running" once looked like a password assignment to the redactor."""
    findings = evaluate(real, [r for r in builtin_rules() if r.id.startswith(STACK_RULES)])
    redacted = redact_snapshot(dataclasses.replace(real, findings=findings), RedactionContext())
    assert not any(item.kind == "secret_value" for item in redacted.redactions)
    desktop = next(f for f in redacted.findings if f.id == "SSD-DESKTOP-001")
    assert desktop.evidence[4].value == "running (pass)"


@pytest.mark.xfail(strict=True, reason="WLD-010")
def test_wireplumber_that_starts_with_pipewire_passes() -> None:
    # Arch with Hyprland: PipeWire is socket-activated and wireplumber.service is enabled
    # (WantedBy=pipewire.service), so it starts together with PipeWire.
    services = ServiceFacts(
        services=(
            UserService("pipewire.service", "loaded", "inactive", unit_file_state="disabled"),
            UserService("pipewire.socket", "loaded", "active", unit_file_state="enabled"),
            UserService("wireplumber.service", "loaded", "inactive", unit_file_state="enabled"),
        )
    )
    finding = _pipewire_case(SKIPPED, services)["SSD-WP-001"]
    assert finding.status is Status.PASS
    assert finding.summary == "WirePlumber starts with PipeWire"
    assert finding.limitations


def test_wireplumber_that_is_not_enabled_stays_unknown() -> None:
    services = ServiceFacts(
        services=(
            UserService("pipewire.socket", "loaded", "active", unit_file_state="enabled"),
            UserService("wireplumber.service", "loaded", "inactive", unit_file_state="disabled"),
        )
    )
    assert _pipewire_case(SKIPPED, services)["SSD-WP-001"].status is Status.UNKNOWN
