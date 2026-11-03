"""The JSON output is a contract: it must match docs/json-schema-v1.json exactly."""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from screenshare_doctor import models
from screenshare_doctor.models import DbusFacts, Snapshot
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.privacy import RedactionContext, redact_snapshot
from screenshare_doctor.reports.json_report import render_json
from tests.unit.test_json_report import real_snapshot

SCHEMA = json.loads((Path(__file__).parents[2] / "docs" / "json-schema-v1.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def validate(document: Any) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
        for e in VALIDATOR.iter_errors(document)
    ]


def test_the_schema_itself_is_valid() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_real_output_matches_the_schema() -> None:
    document = json.loads(render_json(real_snapshot()))
    assert validate(document) == []
    assert len(document["findings"]) == 15


def test_a_broken_machine_matches_the_schema_too() -> None:
    snapshot = diagnose(dataclasses.replace(real_snapshot(), dbus=DbusFacts(reachable=False)))
    assert validate(json.loads(render_json(snapshot))) == []


def test_an_empty_snapshot_matches_the_schema() -> None:
    document = json.loads(
        render_json(Snapshot(tool_version="0.1.0", created_at="2026-11-03T10:00:00Z"))
    )
    assert validate(document) == []


def test_unknown_fields_are_rejected_so_changes_cannot_slip_in() -> None:
    document = json.loads(render_json(real_snapshot()))
    document["session"]["environment"]["new_field"] = "x"
    assert validate(document)


def test_bad_finding_codes_are_rejected() -> None:
    document = json.loads(render_json(real_snapshot()))
    document["findings"][0]["id"] = "GSI-SYS-001"
    assert validate(document)


SCHEMA_DEFS = {
    models.Snapshot: SCHEMA,
    models.SessionFacts: SCHEMA["$defs"]["session"],
    models.SessionEnvironment: SCHEMA["$defs"]["session_environment"],
    models.SessionPaths: SCHEMA["$defs"]["session_paths"],
    models.LogindFacts: SCHEMA["$defs"]["logind"],
    models.LogindSession: SCHEMA["$defs"]["logind_session"],
    models.PackageFacts: SCHEMA["$defs"]["packages"],
    models.PackageInfo: SCHEMA["$defs"]["package"],
    models.ServiceFacts: SCHEMA["$defs"]["services"],
    models.UserService: SCHEMA["$defs"]["user_service"],
    models.XdgDirectories: SCHEMA["$defs"]["xdg_directories"],
    models.DbusFacts: SCHEMA["$defs"]["dbus"],
    models.BusName: SCHEMA["$defs"]["bus_name"],
    models.PortalObject: SCHEMA["$defs"]["portal_object"],
    models.ScreenCastProperties: SCHEMA["$defs"]["screencast_properties"],
    models.PortalFiles: SCHEMA["$defs"]["portal_files"],
    models.PortalsConf: SCHEMA["$defs"]["portals_conf"],
    models.PortalDescriptor: SCHEMA["$defs"]["portal_descriptor"],
    models.PipeWireFacts: SCHEMA["$defs"]["pipewire"],
    models.ProbeFailure: SCHEMA["$defs"]["probe_failure"],
    models.Finding: SCHEMA["$defs"]["finding"],
    models.Evidence: SCHEMA["$defs"]["evidence"],
    models.RedactionCount: SCHEMA["$defs"]["redaction_count"],
}
DERIVED = {models.Snapshot: {"summary"}}


@pytest.mark.parametrize("model", list(SCHEMA_DEFS), ids=lambda m: m.__name__)
def test_every_model_field_is_in_the_schema_and_nothing_else(model: type) -> None:
    fields = {f.name for f in dataclasses.fields(model)} | DERIVED.get(model, set())
    schema = SCHEMA_DEFS[model]
    assert set(schema["properties"]) == fields
    assert set(schema["required"]) == fields
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("enum", "name"),
    [
        (models.Status, "status"),
        (models.Severity, "severity"),
        (models.Confidence, "confidence"),
        (models.Layer, "layer"),
        (models.FailureKind, "failure_kind"),
        (models.PathState, "path_state"),
        (models.PackageState, "package_state"),
    ],
)
def test_enums_match_the_schema(enum: type[Enum], name: str) -> None:
    assert SCHEMA["$defs"][name]["enum"] == [member.value for member in enum]


def test_redacted_output_with_its_redaction_record_matches_the_schema() -> None:
    snapshot = real_snapshot()
    assert snapshot.session is not None
    env = dataclasses.replace(snapshot.session.environment, runtime_dir="/home/alice/.run")
    snapshot = dataclasses.replace(
        snapshot, session=dataclasses.replace(snapshot.session, environment=env)
    )
    redacted = redact_snapshot(snapshot, RedactionContext(home="/home/alice", user="alice"))
    document = json.loads(render_json(redacted))
    assert validate(document) == []
    assert [r["kind"] for r in document["redactions"]] == ["home_path"]
    text = json.dumps(document)
    assert "alice" not in text
    assert "/home/user/" not in text  # another home becomes /home/<user>
    assert "~/.run" in text
