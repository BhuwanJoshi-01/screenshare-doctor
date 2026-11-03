"""Symptom and app profiles for ``troubleshoot screenshare``.

A symptom profile lists the checks that explain it, most likely first; an app profile
adds hints about how that app shares the screen, each with its source. Both are data
(``symptoms.json``, ``apps.json``) so they can be reviewed and extended without code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any


class ProfileDataError(ValueError):
    """A profile file does not have the documented shape."""


@dataclass(frozen=True, slots=True)
class Symptom:
    id: str
    title: str
    explanation: str
    rules: tuple[str, ...]
    limitations: tuple[str, ...] = ()


def _symptom(raw: dict[str, Any]) -> Symptom:
    try:
        return Symptom(
            id=str(raw["id"]),
            title=str(raw["title"]),
            explanation=str(raw["explanation"]),
            rules=tuple(str(code) for code in raw["rules"]),
            limitations=tuple(str(item) for item in raw.get("limitations", ())),
        )
    except (KeyError, TypeError) as exc:
        raise ProfileDataError(f"invalid symptom: {exc}") from None


def parse_symptoms(text: str) -> dict[str, Symptom]:
    symptoms = [_symptom(raw) for raw in json.loads(text)["symptoms"]]
    return {symptom.id: symptom for symptom in symptoms}


def _read(name: str) -> str:
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


@cache
def load_symptoms() -> dict[str, Symptom]:
    """The symptom profiles shipped with the tool, by id, in file order."""
    return parse_symptoms(_read("symptoms.json"))


@dataclass(frozen=True, slots=True)
class Hint:
    """A sourced statement about how an app behaves; ``symptoms`` empty means always shown."""

    text: str
    source: str
    confidence: str
    symptoms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AppProfile:
    id: str
    name: str
    aliases: tuple[str, ...]
    flatpak_ids: tuple[str, ...]
    hints: tuple[Hint, ...]

    def hints_for(self, symptom: str | None) -> tuple[Hint, ...]:
        return tuple(h for h in self.hints if not h.symptoms or symptom in h.symptoms)


@dataclass(frozen=True, slots=True)
class AppProfiles:
    retrieved: str
    apps: dict[str, AppProfile]
    flatpak: Hint

    def find(self, name: str) -> AppProfile | None:
        """The profile whose id, alias or Flatpak id is ``name`` (case does not matter)."""
        wanted = name.strip().lower()
        for app in self.apps.values():
            if wanted == app.id or wanted in app.aliases:
                return app
            if wanted in (flatpak_id.lower() for flatpak_id in app.flatpak_ids):
                return app
        return None


_CONFIDENCE = ("high", "medium", "low")


def _hint(raw: dict[str, Any]) -> Hint:
    hint = Hint(
        text=str(raw["text"]),
        source=str(raw["source"]),
        confidence=str(raw["confidence"]),
        symptoms=tuple(str(s) for s in raw.get("symptoms", ())),
    )
    if hint.confidence not in _CONFIDENCE:
        raise ProfileDataError(f"invalid confidence {hint.confidence!r}")
    return hint


def parse_apps(text: str) -> AppProfiles:
    data = json.loads(text)
    try:
        apps = [
            AppProfile(
                id=str(raw["id"]),
                name=str(raw["name"]),
                aliases=tuple(str(a).lower() for a in raw["aliases"]),
                flatpak_ids=tuple(str(f) for f in raw["flatpak_ids"]),
                hints=tuple(_hint(h) for h in raw["hints"]),
            )
            for raw in data["apps"]
        ]
        return AppProfiles(
            str(data["retrieved"]), {app.id: app for app in apps}, _hint(data["flatpak"])
        )
    except (KeyError, TypeError) as exc:
        raise ProfileDataError(f"invalid app profile: {exc}") from None


@cache
def load_apps() -> AppProfiles:
    """The app profiles shipped with the tool."""
    return parse_apps(_read("apps.json"))
