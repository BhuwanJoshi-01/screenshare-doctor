"""The conclusion of `troubleshoot screenshare` when some of the symptom's checks could not run."""

from __future__ import annotations

import pytest
from rich.console import Console

from screenshare_doctor.models import Confidence, Finding, Severity, Snapshot, Status
from screenshare_doctor.reports.troubleshoot import render_troubleshooting
from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.troubleshoot import load_apps, load_symptoms
from screenshare_doctor.troubleshoot.select import troubleshoot


def _finding(code: str, status: Status, summary: str) -> Finding:
    return Finding(
        id=code,
        status=status,
        severity=Severity.INFO,
        confidence=Confidence.HIGH,
        summary=summary,
        reason="r",
    )


def _render(findings: tuple[Finding, ...]) -> str:
    result = troubleshoot(
        findings,
        symptom=load_symptoms()["missing-window"],
        app_name="firefox",
        apps=load_apps(),
    )
    console = Console(record=True, width=200, highlight=False)
    snapshot = Snapshot(tool_version="0.1.0", created_at="x", findings=findings)
    render_troubleshooting(snapshot, result, builtin_rules(), console)
    return " ".join(console.export_text().split())


PASSING = (
    _finding("SSD-PORTAL-002", Status.PASS, "ScreenCast goes to the hyprland backend"),
    _finding("SSD-DESKTOP-001", Status.PASS, "The setup matches Hyprland's defaults"),
    _finding("SSD-SESSION-002", Status.PASS, "The Wayland display is reachable"),
)


@pytest.mark.xfail(strict=True, reason="WLD-010")
def test_checks_that_did_not_run_are_named_instead_of_blaming_the_app() -> None:
    not_run = _finding(
        "SSD-PORTAL-004",
        Status.NOT_TESTED,
        "Window sharing was not checked: the portal is not running",
    )
    out = _render((not_run, *PASSING))
    assert "SSD-PORTAL-004" in out
    assert "probably in the app" not in out
    assert "1 of these checks could not run (SSD-PORTAL-004)" in out


def test_all_checks_passing_still_points_at_the_app() -> None:
    passing = (_finding("SSD-PORTAL-004", Status.PASS, "ScreenCast offers monitor, window"),)
    out = _render(passing + PASSING)
    assert "None of these checks found a problem. The cause is probably in the app itself" in out
