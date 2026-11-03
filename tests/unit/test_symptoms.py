"""Symptom profiles (WLD-006)."""

from __future__ import annotations

import json
import re

import pytest

from screenshare_doctor.rules.catalog import builtin_rules
from screenshare_doctor.troubleshoot import ProfileDataError, load_symptoms, parse_symptoms


def test_the_documented_symptoms_exist() -> None:
    assert list(load_symptoms()) == [
        "no-picker",
        "black-screen",
        "missing-window",
        "permission-denied",
        "app-only",
    ]


@pytest.mark.parametrize("symptom_id", list(load_symptoms()))
def test_every_symptom_points_at_real_checks(symptom_id: str) -> None:
    symptom = load_symptoms()[symptom_id]
    codes = {rule.id for rule in builtin_rules()}
    assert symptom.rules
    assert len(set(symptom.rules)) == len(symptom.rules)
    for code in symptom.rules:
        assert code in codes, f"{symptom_id} names unknown check {code}"
    assert re.fullmatch(r"[a-z]+(-[a-z]+)*", symptom.id)
    assert symptom.title
    assert symptom.explanation


def test_malformed_profiles_are_rejected() -> None:
    with pytest.raises(ProfileDataError):
        parse_symptoms(json.dumps({"symptoms": [{"id": "x"}]}))
