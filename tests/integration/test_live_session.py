"""Against this machine's real session, opt-in: SSD_INTEGRATION=1 uv run pytest tests/integration.

These tests run the real collectors. They check the passive promise from the outside:
the set of running bus names and active user units is the same before and after a
full diagnosis. Run them in a desktop session; they change nothing.
"""

from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

pytestmark = pytest.mark.skipif(
    os.environ.get("SSD_INTEGRATION") != "1", reason="set SSD_INTEGRATION=1 to test this machine"
)

SCHEMA = json.loads((Path(__file__).parents[2] / "docs" / "json-schema-v1.json").read_text())


def _lines(*argv: str) -> set[str]:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)  # noqa: S603
    return set(result.stdout.splitlines())


def _running_bus_names() -> set[str]:
    names = set()
    for line in _lines("busctl", "--user", "list", "--no-legend", "--no-pager"):
        parts = line.split()
        if len(parts) > 1 and parts[1] != "-" and not parts[0].startswith(":"):
            names.add(parts[0])
    return names


def _active_units() -> set[str]:
    return {
        line.split()[0]
        for line in _lines(
            "systemctl",
            "--user",
            "list-units",
            "--state=active",
            "--no-legend",
            "--no-pager",
            "--plain",
        )
        if line.strip()
    }


def _doctor_json() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "screenshare_doctor", "doctor", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    document: dict[str, object] = json.loads(result.stdout)
    return document


@pytest.mark.skipif(shutil.which("busctl") is None, reason="needs busctl")
def test_doctor_starts_no_service() -> None:
    names_before, units_before = _running_bus_names(), _active_units()
    _doctor_json()
    assert _running_bus_names() == names_before
    assert _active_units() == units_before


def test_real_report_matches_the_schema() -> None:
    document = _doctor_json()
    errors = [e.message for e in Draft202012Validator(SCHEMA).iter_errors(document)]
    assert errors == []
    assert document["findings"]


def test_real_report_contains_no_user_name() -> None:
    user = getpass.getuser()
    if len(user) < 4:
        pytest.skip("user name too short to search for")
    text = json.dumps(_doctor_json())
    assert user not in text
    assert str(Path.home()) not in text
