"""Render a troubleshoot run as an SVG for the README and the site (maintainer tool, not shipped).

    uv run python scripts/render_demo.py OUT.svg

The run uses the real captures of the Ubuntu 26.04 / GNOME 50.1 machine in tests/fixtures,
plus one user file that copies a Hyprland setup and disables ScreenCast, a mistake seen in
real reports. It is redacted like every report and printed by the real renderer; Rich then
exports what was printed.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screenshare_doctor.collectors.pipewire import collect_pipewire
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.reports.troubleshoot import render_troubleshooting
from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.troubleshoot import load_apps, load_symptoms
from screenshare_doctor.troubleshoot.select import troubleshoot
from tests.fakes import FakeRunner
from tests.scenarios import gnome_snapshot, script_gnome_pipewire

OVERRIDE = {
    "/home/user/.config/xdg-desktop-portal/portals.conf": (
        b"[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.ScreenCast=none\n"
    )
}


def main(out: Path) -> None:
    snapshot = gnome_snapshot(OVERRIDE)
    runner = FakeRunner()
    script_gnome_pipewire(runner)
    pipewire, _ = collect_pipewire(runner, snapshot.services)
    diagnosed = diagnose(dataclasses.replace(snapshot, pipewire=pipewire))
    redacted = redact_snapshot(diagnosed, RedactionContext(home="/home/user", user="user"))
    apps = load_apps()
    result = troubleshoot(
        redacted.findings, symptom=load_symptoms()["no-picker"], app_name="discord", apps=apps
    )
    console = Console(record=True, width=104, force_terminal=True, color_system="truecolor")
    console.print("$ screenshare-doctor troubleshoot screenshare --app discord --symptom no-picker")
    render_troubleshooting(redacted, result, builtin_rules(), console)
    out.write_text(console.export_svg(title="screenshare-doctor"), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
