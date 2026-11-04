"""The PipeWire and WirePlumber layers: where the screen cast stream ends up."""

from __future__ import annotations

from collections.abc import Iterator

from screenshare_doctor.models import (
    Confidence,
    Evidence,
    FailureKind,
    Finding,
    Layer,
    PackageState,
    Severity,
    Snapshot,
    Status,
    UserService,
)
from screenshare_doctor.rules.catalog import RULES
from screenshare_doctor.rules.engine import RuleContext


def _unit(snapshot: Snapshot, name: str) -> UserService | None:
    services = snapshot.services
    if services is None or services.services is None:
        return None
    return next((s for s in services.services if s.unit == name and s.load_state), None)


_UNUSABLE = (FailureKind.NOT_FOUND, FailureKind.PERMISSION_DENIED, FailureKind.MALFORMED_OUTPUT)
"""pw-dump failures that say nothing about the daemon: the tool, not PipeWire, failed."""


def _pw_dump_unusable(snapshot: Snapshot) -> FailureKind | None:
    failure = next((f for f in snapshot.probe_failures if f.probe == "pw-dump"), None)
    return failure.kind if failure is not None and failure.kind in _UNUSABLE else None


def _package_missing(snapshot: Snapshot, name: str) -> bool:
    packages = snapshot.packages
    info = next((p for p in packages.packages if p.name == name), None) if packages else None
    return info is not None and info.state is PackageState.NOT_INSTALLED


@RULES.rule("SSD-PW-001", "PipeWire can carry the screen cast", layer=Layer.PIPEWIRE)
def pipewire(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether the PipeWire daemon runs, or can start on demand.

    A Wayland screen cast is a PipeWire stream: the backend creates it, the app reads
    it. With systemd, PipeWire normally starts on demand through pipewire.socket, so a
    stopped service with an active socket is fine. PipeWire is only asked when it
    already runs, because asking would start it.
    """
    facts = snapshot.pipewire
    if facts is None:
        return
    service, socket = _unit(snapshot, "pipewire.service"), _unit(snapshot, "pipewire.socket")
    evidence = (
        Evidence("systemctl", "pipewire.service", service.active_state if service else None),
        Evidence("systemctl", "pipewire.socket", socket.active_state if socket else None),
        Evidence("pw-dump", "version", facts.version),
    )
    verify = "systemctl --user status pipewire.service pipewire.socket"
    if facts.version is not None or facts.clients is not None:
        yield Finding(
            id="SSD-PW-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.HIGH,
            summary=f"PipeWire {facts.version or ''} answers".replace("  ", " "),
            reason="pw-dump reached the daemon.",
            evidence=evidence,
        )
    elif _package_missing(snapshot, "pipewire"):
        yield Finding(
            id="SSD-PW-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary="PipeWire is not installed",
            reason="Without PipeWire no screen cast stream can be created.",
            evidence=evidence,
            recommended_action="Install pipewire (and wireplumber) with your package manager.",
        )
    elif facts.skipped is not None:
        if socket is not None and socket.active_state == "active":
            yield Finding(
                id="SSD-PW-001",
                status=Status.PASS,
                severity=Severity.INFO,
                confidence=Confidence.MEDIUM,
                summary="PipeWire starts on demand",
                reason="pipewire.service is not running, but pipewire.socket is active.",
                evidence=evidence,
                limitations=(
                    "PipeWire was not asked, so it is not known whether it starts cleanly.",
                ),
            )
        elif service is not None and service.active_state == "failed":
            yield Finding(
                id="SSD-PW-001",
                status=Status.FAIL,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                summary="pipewire.service has failed",
                reason="Its last start failed, and nothing else carries screen casts.",
                evidence=evidence,
                recommended_action="Read why: journalctl --user -u pipewire.service -b",
                verify_command=verify,
            )
        elif service is not None and socket is not None:
            yield Finding(
                id="SSD-PW-001",
                status=Status.FAIL,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                summary="PipeWire is not running and cannot start on demand",
                reason=(
                    f"pipewire.service is {service.active_state} and pipewire.socket is "
                    f"{socket.active_state}."
                ),
                evidence=evidence,
                recommended_action="systemctl --user enable --now pipewire.socket pipewire.service",
                verify_command=verify,
            )
        else:
            yield Finding(
                id="SSD-PW-001",
                status=Status.UNKNOWN,
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                summary="PipeWire was not checked",
                reason=facts.skipped,
                evidence=evidence,
            )
    elif (unusable := _pw_dump_unusable(snapshot)) is not None:
        missing = unusable is FailureKind.NOT_FOUND
        yield Finding(
            id="SSD-PW-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            summary=(
                "PipeWire runs, but pw-dump is not installed to ask it"
                if missing
                else "PipeWire runs, but pw-dump's answer could not be used"
            ),
            reason=(
                "pipewire.service is "
                f"{service.active_state if service else 'in an unknown state'}; "
                + (
                    "whether the daemon answers is not known without pw-dump."
                    if missing
                    else "pw-dump failed (see the probe failures), which says nothing about "
                    "the daemon itself."
                )
            ),
            evidence=evidence,
            recommended_action=(
                "Install the package with pw-dump (pipewire-utils on Fedora, pipewire-bin on "
                "Debian and Ubuntu, pipewire-tools on openSUSE; Arch ships it with pipewire), "
                "then run the check again."
                if missing
                else None
            ),
            verify_command="pw-dump --version",
        )
    elif service is not None and service.active_state == "active":
        yield Finding(
            id="SSD-PW-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            summary="PipeWire runs but does not answer",
            reason=(
                "pipewire.service is active, but pw-dump got no answer (see the probe failures)."
            ),
            evidence=evidence,
            verify_command="pw-cli info 0",
        )
    else:
        yield Finding(
            id="SSD-PW-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="PipeWire could not be checked",
            reason="pw-dump did not answer and the service state is unknown.",
            evidence=evidence,
        )


@RULES.rule("SSD-WP-001", "WirePlumber manages the PipeWire graph", layer=Layer.WIREPLUMBER)
def wireplumber(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
    """Whether WirePlumber, PipeWire's session manager, is running and connected.

    Without a session manager PipeWire does not link a new stream to its consumer, and
    some compositors and portals wait for it. Judged from PipeWire's client list when
    PipeWire answered, otherwise from the user service.
    """
    facts, unit = snapshot.pipewire, _unit(snapshot, "wireplumber.service")
    if facts is None and unit is None:
        return
    evidence = (
        Evidence("systemctl", "wireplumber.service", unit.active_state if unit else None),
        Evidence(
            "pw-dump",
            "WirePlumber client",
            None
            if facts is None or facts.clients is None
            else str("WirePlumber" in facts.clients).lower(),
        ),
    )
    verify = "systemctl --user status wireplumber.service"
    if unit is not None and (unit.load_state == "masked" or unit.active_state == "failed"):
        yield Finding(
            id="SSD-WP-001",
            status=Status.FAIL,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            summary=(
                "wireplumber.service is "
                f"{unit.load_state if unit.load_state == 'masked' else 'failed'}"
            ),
            reason="PipeWire has no session manager, so new streams are not linked.",
            evidence=evidence,
            recommended_action="Read why: journalctl --user -u wireplumber.service -b",
            verify_command=verify,
        )
    elif facts is not None and facts.clients is not None:
        if "WirePlumber" in facts.clients:
            yield Finding(
                id="SSD-WP-001",
                status=Status.PASS,
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                summary="WirePlumber is connected to PipeWire",
                reason="It is in PipeWire's client list.",
                evidence=evidence,
            )
        else:
            yield Finding(
                id="SSD-WP-001",
                status=Status.WARN,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                summary="No WirePlumber client on PipeWire",
                reason=(
                    "PipeWire answers but WirePlumber is not among its clients; another session "
                    "manager may be in use."
                ),
                evidence=evidence,
                recommended_action="systemctl --user enable --now wireplumber.service",
                verify_command=verify,
            )
    elif unit is not None and unit.active_state == "active":
        yield Finding(
            id="SSD-WP-001",
            status=Status.PASS,
            severity=Severity.INFO,
            confidence=Confidence.MEDIUM,
            summary="wireplumber.service is active",
            reason="PipeWire itself was not asked.",
            evidence=evidence,
        )
    else:
        yield Finding(
            id="SSD-WP-001",
            status=Status.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            summary="WirePlumber could not be checked",
            reason="Neither PipeWire's client list nor an active user service is known.",
            evidence=evidence,
        )
