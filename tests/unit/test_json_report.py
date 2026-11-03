"""JSON output (WLD-008)."""

from __future__ import annotations

import dataclasses
import json

from screenshare_doctor.collectors.pipewire import collect_pipewire
from screenshare_doctor.models import Confidence, DbusFacts, Finding, Severity, Snapshot, Status
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.reports.json_report import render_json, snapshot_to_dict, summary
from tests.fakes import FakeRunner
from tests.scenarios import gnome_snapshot, script_gnome_pipewire


def real_snapshot() -> Snapshot:
    snapshot = gnome_snapshot()
    runner = FakeRunner()
    script_gnome_pipewire(runner)
    pipewire, _ = collect_pipewire(runner, snapshot.services)
    return diagnose(dataclasses.replace(snapshot, pipewire=pipewire))


def test_real_machine_summary() -> None:
    assert summary(real_snapshot()) == {
        "session": "wayland",
        "location": "desktop",
        "desktop_family": "gnome",
        "desktop_name": "gnome",
        "portal_version": "1.21.1+ds-1ubuntu3.1",
        "counts": {
            "pass": 15,
            "warn": 0,
            "fail": 0,
            "unknown": 0,
            "not_applicable": 0,
            "not_tested": 0,
        },
        "worst": "pass",
    }


def test_worst_status_orders_failures_first() -> None:
    def finding(code: str, status: Status) -> Finding:
        return Finding(code, status, Severity.LOW, Confidence.HIGH, "x", "y")

    snapshot = Snapshot(
        tool_version="0.1.0",
        created_at="x",
        findings=(finding("SSD-A-001", Status.UNKNOWN), finding("SSD-B-001", Status.WARN)),
    )
    assert summary(snapshot)["worst"] == "warn"
    assert summary(Snapshot(tool_version="0.1.0", created_at="x"))["worst"] is None


def test_json_round_trips_and_uses_documented_strings() -> None:
    document = json.loads(render_json(real_snapshot()))
    assert document["schema_version"] == 1
    assert document["findings"][0]["status"] == "pass"
    assert document["findings"][0]["layer"] == "session"
    assert document["session"]["paths"]["wayland_socket"] == "socket"
    assert document["portal_files"]["configs"][0]["preferred"][0] == ["default", ["gnome", "gtk"]]


def test_unreachable_bus_is_visible_in_json() -> None:
    snapshot = diagnose(dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=False)))
    document = snapshot_to_dict(snapshot)
    assert document["dbus"]["reachable"] is False
    assert document["summary"]["worst"] == "fail"
    portal = next(f for f in document["findings"] if f["id"] == "SSD-PORTAL-001")
    assert portal["caused_by"] == "SSD-DBUS-001"


def test_output_ends_with_a_newline_and_keeps_unicode() -> None:
    finding = Finding(
        "SSD-A-001", Status.PASS, Severity.INFO, Confidence.HIGH, "Bildschirm geteilt …", "ok"
    )
    text = render_json(Snapshot(tool_version="0.1.0", created_at="x", findings=(finding,)))
    assert text.endswith("}\n")
    assert "Bildschirm geteilt …" in text
