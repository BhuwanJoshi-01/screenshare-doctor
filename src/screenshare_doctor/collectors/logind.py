"""Ask systemd-logind which session is the user's desktop, read-only.

The tool's own environment is not always the desktop's: a terminal started by the user
manager (VS Code, a terminal launched through D-Bus activation) has no ``XDG_SESSION_ID``,
and an SSH login belongs to a different session altogether. logind still knows the
graphical session, and ``loginctl show-*`` reads it without privileges or side effects.
"""

from __future__ import annotations

from screenshare_doctor.models import LogindSession

SESSION_PROPERTIES: tuple[str, ...] = (
    "Id",
    "Type",
    "Class",
    "Remote",
    "Desktop",
    "State",
    "Active",
    "Seat",
)


def parse_properties(text: str) -> dict[str, str]:
    """``Key=value`` lines as printed by ``loginctl show-*``; other lines are skipped."""
    properties: dict[str, str] = {}
    for line in text.splitlines():
        key, equals, value = line.partition("=")
        if equals and key and key.isidentifier():
            properties[key] = value.strip()
    return properties


def parse_session(text: str) -> LogindSession | None:
    """A :class:`LogindSession` from ``show-session`` output, or ``None`` without an ``Id``."""
    properties = parse_properties(text)
    session_id = properties.get("Id")
    if not session_id:
        return None

    def value(key: str) -> str | None:
        return properties.get(key) or None

    return LogindSession(
        id=session_id,
        session_type=value("Type"),
        session_class=value("Class"),
        desktop=value("Desktop"),
        remote=_boolean(properties.get("Remote")),
        active=_boolean(properties.get("Active")),
        state=value("State"),
        seat=value("Seat"),
    )


def _boolean(value: str | None) -> bool | None:
    return {"yes": True, "no": False}.get(value or "")
