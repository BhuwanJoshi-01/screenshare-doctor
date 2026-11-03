"""App profiles (WLD-006)."""

from __future__ import annotations

import json

import pytest

from screenshare_doctor.troubleshoot import ProfileDataError, load_apps, load_symptoms, parse_apps


def test_profiles_and_lookup() -> None:
    apps = load_apps()
    assert list(apps.apps) == ["firefox", "chromium", "electron", "obs"]
    assert apps.find("Discord") is apps.apps["electron"]
    assert apps.find("google-chrome") is apps.apps["chromium"]
    assert apps.find("org.mozilla.firefox") is apps.apps["firefox"]
    assert apps.find("com.obsproject.Studio") is apps.apps["obs"]
    assert apps.find("zoom") is None


@pytest.mark.parametrize("app_id", list(load_apps().apps))
def test_every_hint_is_sourced(app_id: str) -> None:
    app = load_apps().apps[app_id]
    assert app.hints
    symptoms = set(load_symptoms())
    for hint in app.hints:
        assert hint.source.startswith("https://")
        assert set(hint.symptoms) <= symptoms
        assert hint.text.endswith(".")


def test_aliases_are_unique_across_apps() -> None:
    seen: dict[str, str] = {}
    for app in load_apps().apps.values():
        for name in (app.id, *app.aliases, *(f.lower() for f in app.flatpak_ids)):
            assert seen.setdefault(name, app.id) == app.id, name


def test_hints_for_a_symptom() -> None:
    electron = load_apps().apps["electron"]
    assert len(electron.hints_for("app-only")) == 2  # one specific, one general
    assert len(electron.hints_for("black-screen")) == 1
    assert len(electron.hints_for(None)) == 1


def test_flatpak_hint() -> None:
    assert load_apps().flatpak.source.startswith("https://docs.flatpak.org/")


def test_malformed_profiles_are_rejected() -> None:
    with pytest.raises(ProfileDataError):
        parse_apps(json.dumps({"retrieved": "x", "apps": [{"id": "a"}], "flatpak": {}}))
    bad = {"text": "x.", "source": "https://x", "confidence": "certain"}
    with pytest.raises(ProfileDataError):
        parse_apps(json.dumps({"retrieved": "x", "apps": [], "flatpak": bad}))
