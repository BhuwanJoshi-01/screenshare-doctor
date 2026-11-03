"""Ask systemd-logind which session is the user's desktop, read-only.

The tool's own environment is not always the desktop's: a terminal started by the user
manager (VS Code, a terminal launched through D-Bus activation) has no ``XDG_SESSION_ID``,
and an SSH login belongs to a different session altogether. logind still knows the
graphical session, and ``loginctl show-*`` reads it without privileges or side effects.
"""

from __future__ import annotations

import re

from screenshare_doctor.models import (
    FailureKind,
    LogindFacts,
    LogindSession,
    ProbeFailure,
    SessionEnvironment,
)
from screenshare_doctor.runner import CommandRunner, probe_failure

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


LOGINCTL_TIMEOUT = 5.0
"""Seconds; logind answers in milliseconds unless the system bus is stuck."""

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", re.ASCII)
"""logind session ids look like ``2``, ``63`` or ``c1``. Anything else is not passed on,
above all a value starting with ``-``, which loginctl would read as an option."""


def collect_logind(
    runner: CommandRunner, env: SessionEnvironment, *, uid: int
) -> tuple[LogindFacts, tuple[ProbeFailure, ...]]:
    """Read the tool's own session and the user's graphical session from logind.

    Runs at most three ``loginctl show-*`` commands and stops at the first sign that
    loginctl is missing. Without systemd or elogind everything stays unknown.
    """
    failures: list[ProbeFailure] = []
    own: LogindSession | None = None
    if env.session_id is not None:
        if _SESSION_ID.fullmatch(env.session_id):
            own, failure = _show_session(runner, env.session_id)
            if failure is not None:
                failures.append(failure)
                if failure.kind is FailureKind.NOT_FOUND:
                    return LogindFacts(), tuple(failures)
        else:
            failures.append(
                ProbeFailure(
                    "loginctl show-session",
                    FailureKind.MALFORMED_OUTPUT,
                    "XDG_SESSION_ID does not look like a logind session id; not asked about",
                )
            )

    result = runner.run(
        ["loginctl", "--no-pager", "show-user", str(uid), "-p", "Display"],
        timeout=LOGINCTL_TIMEOUT,
    )
    failure = probe_failure("loginctl show-user", result)
    if failure is not None:
        failures.append(failure)
        return LogindFacts(own=own), tuple(failures)
    display_id = parse_properties(result.stdout).get("Display", "")
    if not display_id:
        return LogindFacts(own=own, display_known=True), tuple(failures)
    if own is not None and own.id == display_id:
        return LogindFacts(own=own, display=own, display_known=True), tuple(failures)
    if not _SESSION_ID.fullmatch(display_id):
        failures.append(
            ProbeFailure(
                "loginctl show-user",
                FailureKind.MALFORMED_OUTPUT,
                "the Display property is not a session id",
            )
        )
        return LogindFacts(own=own), tuple(failures)
    display, failure = _show_session(runner, display_id)
    if failure is not None:
        failures.append(failure)
    return LogindFacts(own=own, display=display, display_known=display is not None), tuple(failures)


def _show_session(
    runner: CommandRunner, session_id: str
) -> tuple[LogindSession | None, ProbeFailure | None]:
    argv = ["loginctl", "--no-pager", "show-session", session_id]
    for name in SESSION_PROPERTIES:
        argv += ["-p", name]
    result = runner.run(argv, timeout=LOGINCTL_TIMEOUT)
    failure = probe_failure("loginctl show-session", result)
    if failure is not None:
        return None, failure
    session = parse_session(result.stdout)
    if session is None:
        return None, ProbeFailure(
            "loginctl show-session", FailureKind.MALFORMED_OUTPUT, "no Id in the output"
        )
    return session, None
