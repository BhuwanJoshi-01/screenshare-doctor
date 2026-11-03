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
