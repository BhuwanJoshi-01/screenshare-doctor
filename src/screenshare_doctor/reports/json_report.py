"""JSON output: the snapshot as plain data, for scripts, CI, bug reports and the extension."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from screenshare_doctor.desktops import identify_desktop
from screenshare_doctor.models import Snapshot, Status
from screenshare_doctor.reports.terminal import portal_version
from screenshare_doctor.session import assess_session

WORST_FIRST = (
    Status.FAIL,
    Status.WARN,
    Status.UNKNOWN,
    Status.PASS,
    Status.NOT_TESTED,
    Status.NOT_APPLICABLE,
)
"""Order used for ``summary.worst``: the status a top-bar icon should show."""


def summary(snapshot: Snapshot) -> dict[str, Any]:
    """Derived values that readers look for first; every one follows from the facts."""
    session_kind = location = None
    if snapshot.session is not None:
        facts = snapshot.session
        result = assess_session(facts.environment, facts.paths, facts.logind)
        session_kind, location = result.kind.value, result.location.value
    env = snapshot.services.activation_environment if snapshot.services else None
    if env is None and snapshot.session is not None:
        env = snapshot.session.environment
    family = name = None
    if env is not None:
        identity = identify_desktop(env)
        family, name = identity.family.value, identity.name
    counts = Counter(finding.status for finding in snapshot.findings)
    worst = next((status.value for status in WORST_FIRST if counts.get(status)), None)
    return {
        "session": session_kind,
        "location": location,
        "desktop_family": family,
        "desktop_name": name,
        "portal_version": portal_version(snapshot),
        "counts": {status.value: counts.get(status, 0) for status in Status},
        "worst": worst,
    }


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    """Plain dicts, lists and scalars; enums become their documented string values."""
    plain = _plain(snapshot)
    if not isinstance(plain, dict):  # cannot happen: a dataclass becomes a dict
        raise TypeError("snapshot did not serialise to an object")
    plain["summary"] = summary(snapshot)
    return plain


def render_json(snapshot: Snapshot) -> str:
    """Indented JSON with a trailing newline. Pass a redacted snapshot."""
    return json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value
