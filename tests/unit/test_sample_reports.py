"""The sample reports in docs/ are what the current code renders."""

from __future__ import annotations

import dataclasses

from screenshare_doctor.collectors.pipewire import collect_pipewire
from screenshare_doctor.models import Snapshot
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.reports.json_report import render_json
from screenshare_doctor.reports.markdown import render_markdown
from tests.fakes import FIXTURES, FakeRunner
from tests.scenarios import gnome_snapshot, script_gnome_pipewire

SAMPLES = FIXTURES.parent.parent / "docs" / "sample-reports"
CONTEXT = RedactionContext(home="/home/user", user="user")
DISABLED = {
    "/home/user/.config/xdg-desktop-portal/portals.conf": (
        b"[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.ScreenCast=none\n"
    )
}


def _sample(extra: dict[str, bytes] | None = None) -> Snapshot:
    snapshot = gnome_snapshot(extra)
    runner = FakeRunner()
    script_gnome_pipewire(runner)
    pipewire, _ = collect_pipewire(runner, snapshot.services)
    diagnosed = diagnose(dataclasses.replace(snapshot, pipewire=pipewire))
    return redact_snapshot(
        dataclasses.replace(diagnosed, created_at="2026-11-03T12:00:00Z"), CONTEXT
    )


def test_healthy_samples_are_current() -> None:
    snapshot = _sample()
    assert (SAMPLES / "gnome-healthy.md").read_text(encoding="utf-8") == render_markdown(snapshot)
    assert (SAMPLES / "gnome-healthy.json").read_text(encoding="utf-8") == render_json(snapshot)


def test_broken_sample_is_current() -> None:
    expected = render_markdown(_sample(DISABLED))
    assert (SAMPLES / "gnome-screencast-disabled.md").read_text(encoding="utf-8") == expected
