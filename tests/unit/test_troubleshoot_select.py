"""Selecting the findings for an app and a symptom (WLD-006)."""

from __future__ import annotations

import dataclasses

from screenshare_doctor.models import DbusFacts, Finding, Snapshot, Status
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.troubleshoot import load_apps, load_symptoms
from screenshare_doctor.troubleshoot.select import troubleshoot
from tests.scenarios import gnome_snapshot

SYMPTOMS = load_symptoms()
APPS = load_apps()


def _findings(snapshot: Snapshot) -> tuple[Finding, ...]:
    return diagnose(snapshot).findings


def test_real_machine_with_no_picker_finds_nothing_wrong() -> None:
    result = troubleshoot(
        _findings(gnome_snapshot()), symptom=SYMPTOMS["no-picker"], app_name="firefox", apps=APPS
    )
    assert [f.id for f in result.relevant] == list(SYMPTOMS["no-picker"].rules)
    assert result.likely is None
    assert result.app is APPS.apps["firefox"]
    assert len(result.hints) == 2


def test_order_follows_the_symptom() -> None:
    result = troubleshoot(
        _findings(gnome_snapshot()), symptom=SYMPTOMS["black-screen"], app_name=None, apps=APPS
    )
    assert result.relevant[0].id == "SSD-COMPOSITOR-001"


def test_most_likely_cause_is_the_first_relevant_failure() -> None:
    user_file = "/home/user/.config/xdg-desktop-portal/gnome-portals.conf"
    disabled = {user_file: b"[preferred]\norg.freedesktop.impl.portal.ScreenCast=none\n"}
    result = troubleshoot(
        _findings(gnome_snapshot(disabled)),
        symptom=SYMPTOMS["no-picker"],
        app_name="discord",
        apps=APPS,
    )
    assert result.likely is not None
    assert result.likely.id == "SSD-PORTAL-002"
    assert result.app is APPS.apps["electron"]


def test_root_cause_is_shown_instead_of_the_cascade() -> None:
    snapshot = dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=False))
    result = troubleshoot(
        _findings(snapshot), symptom=SYMPTOMS["no-picker"], app_name=None, apps=APPS
    )
    ids = [f.id for f in result.relevant]
    assert "SSD-DBUS-001" in ids
    assert "SSD-PORTAL-001" not in ids
    assert result.likely is not None
    assert result.likely.id == "SSD-DBUS-001"


def test_problems_outside_the_symptom_are_kept() -> None:
    snapshot = dataclasses.replace(gnome_snapshot(), dbus=DbusFacts(reachable=False))
    result = troubleshoot(
        _findings(snapshot), symptom=SYMPTOMS["missing-window"], app_name=None, apps=APPS
    )
    assert "SSD-DBUS-001" in [f.id for f in result.others]
    assert all(f.status is not Status.PASS for f in result.others)


def test_without_a_symptom_every_check_is_relevant() -> None:
    findings = _findings(gnome_snapshot())
    result = troubleshoot(findings, symptom=None, app_name=None, apps=APPS)
    assert len(result.relevant) == len(findings)
    assert result.others == ()


def test_unknown_app_gets_no_hints() -> None:
    result = troubleshoot((), symptom=None, app_name="zoom", apps=APPS)
    assert (result.app, result.hints) == (None, ())
    assert result.app_name == "zoom"


def test_flatpak_adds_the_portal_hint() -> None:
    result = troubleshoot(
        (), symptom=None, app_name="discord", apps=APPS, flatpak=("com.discordapp.Discord",)
    )
    assert result.hints[-1] is APPS.flatpak
