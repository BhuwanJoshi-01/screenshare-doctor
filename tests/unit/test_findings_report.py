"""The doctor report in the terminal."""

from __future__ import annotations

import dataclasses

from rich.console import Console

from screenshare_doctor.collectors.pipewire import collect_pipewire
from screenshare_doctor.models import (
    Confidence,
    DbusFacts,
    Finding,
    Severity,
    Snapshot,
    Status,
)
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.reports.findings import headline, render_findings
from tests.fakes import FakeRunner
from tests.scenarios import gnome_snapshot, script_gnome_pipewire


def _real() -> Snapshot:
    snapshot = gnome_snapshot()
    runner = FakeRunner()
    script_gnome_pipewire(runner)
    pipewire, _ = collect_pipewire(runner, snapshot.services)
    return diagnose(dataclasses.replace(snapshot, pipewire=pipewire))


def _render(snapshot: Snapshot, *, show_all: bool = False) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as capture:
        render_findings(snapshot, console, show_all=show_all)
    return capture.get()


def test_real_machine_report() -> None:
    out = _render(_real())
    assert "Session: Wayland | Desktop: GNOME | Portal: 1.21.1+ds-1ubuntu3.1" in out
    assert "PASS    SSD-SESSION-001    Wayland session" in out
    assert "PASS    SSD-WP-001         WirePlumber is connected to PipeWire" in out
    assert "Summary: 15 pass, 0 warn, 0 fail, 0 unknown" in out
    assert "Nothing was started, changed or recorded" in out
    assert "Next:" not in out  # passes get one line only


def test_failures_show_reason_next_step_and_check() -> None:
    finding = Finding(
        id="SSD-PORTAL-002",
        status=Status.FAIL,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="No installed backend implements ScreenCast",
        reason="Nothing leads to a backend.",
        recommended_action="Install your desktop's portal backend.",
        verify_command="screenshare-doctor routes explain",
        limitations=("Only the newest rules were applied.",),
    )
    out = _render(Snapshot(tool_version="0.1.0", created_at="x", findings=(finding,)))
    assert "FAIL    SSD-PORTAL-002     No installed backend implements ScreenCast" in out
    assert "Nothing leads to a backend." in out
    assert "Next: Install your desktop's portal backend." in out
    assert "Check: screenshare-doctor routes explain" in out
    assert "Note: Only the newest rules were applied." in out
    assert "Summary: 0 pass, 0 warn, 1 fail, 0 unknown" in out


def test_cascade_is_folded_under_its_root_cause() -> None:
    snapshot = diagnose(dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=False)))
    out = _render(snapshot)
    assert "FAIL    SSD-DBUS-001       The session bus does not answer" in out
    assert "SSD-PORTAL-001" not in out
    assert "follow from the ones above and are not shown (--all shows them)" in out
    everything = _render(snapshot, show_all=True)
    folded = "SSD-PORTAL-001     The portal frontend was not checked (follows from SSD-DBUS-001)"
    assert folded in everything


def test_markup_in_findings_is_printed_literally() -> None:
    finding = Finding(
        id="SSD-SESSION-003",
        status=Status.WARN,
        severity=Severity.LOW,
        confidence=Confidence.HIGH,
        summary="[bold red]desktop[/]",
        reason="[link=x]y[/link]",
    )
    out = _render(Snapshot(tool_version="0.1.0", created_at="x", findings=(finding,)))
    assert "[bold red]desktop[/]" in out
    assert "[link=x]y[/link]" in out


def test_headline_without_facts_is_empty() -> None:
    assert headline(Snapshot(tool_version="0.1.0", created_at="x")) == ""
