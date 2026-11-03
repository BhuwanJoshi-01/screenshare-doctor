"""Typed facts and findings shared by collectors, rules and renderers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

SCHEMA_VERSION = 1
"""Version of the snapshot/JSON report layout; bumped only for incompatible changes."""

FINDING_ID = re.compile(r"SSD-[A-Z]+-[0-9]{3}")
"""Finding codes are part of the public contract: ``SSD-<AREA>-<NNN>``, e.g. ``SSD-PORTAL-002``."""


class Status(StrEnum):
    """Outcome of one check.

    Only ``PASS`` means that a check ran and succeeded. A check that could not run is
    ``UNKNOWN``; one that was deliberately skipped (an opt-in probe nobody asked for) is
    ``NOT_TESTED``; one that does not apply to this machine is ``NOT_APPLICABLE``.
    """

    PASS = "pass"  # noqa: S105 - a status name, not a password
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    NOT_TESTED = "not_tested"


class Severity(StrEnum):
    """How much a finding matters to the user's goal, independent of certainty."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(StrEnum):
    """How well the evidence supports a finding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Layer(StrEnum):
    """The part of the screen-sharing stack a finding is about, from the session up to the app.

    Screen sharing breaks in one of these layers; naming it is the point of a diagnosis.
    """

    SESSION = "session"
    DBUS = "dbus"
    PORTAL_FRONTEND = "portal-frontend"
    PORTAL_BACKEND = "portal-backend"
    COMPOSITOR = "compositor"
    PIPEWIRE = "pipewire"
    WIREPLUMBER = "wireplumber"
    APP = "app"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observed fact that a finding relies on.

    ``source`` names where the fact came from (``busctl``, ``portals.conf``…), ``key``
    what it is (``owner``, ``ScreenCast.version``…). ``value`` is ``None`` when the fact
    is missing, which is itself evidence.
    """

    source: str
    key: str
    value: str | None


@dataclass(frozen=True, slots=True)
class Finding:
    """A diagnosis with everything a user needs to judge and verify it.

    ``subject`` says what the finding is about: ``session`` or the app it concerns.
    ``layer`` is the part of the screen-sharing stack it is about. ``verify_command`` is a
    command the user can run to check the result after acting on ``recommended_action``.
    ``caused_by`` names the finding this one follows from (``SSD-DBUS-001`` for "portal
    not checked because the session bus is unreachable"), so reports show one root cause
    instead of a cascade.
    """

    id: str
    status: Status
    severity: Severity
    confidence: Confidence
    summary: str
    reason: str
    subject: str = "session"
    layer: Layer | None = None
    evidence: tuple[Evidence, ...] = ()
    recommended_action: str | None = None
    verify_command: str | None = None
    limitations: tuple[str, ...] = ()
    caused_by: str | None = None

    def __post_init__(self) -> None:
        if not FINDING_ID.fullmatch(self.id):
            raise ValueError(f"finding id {self.id!r} does not match SSD-<AREA>-<NNN>")
        if self.caused_by is not None and not FINDING_ID.fullmatch(self.caused_by):
            raise ValueError(f"caused_by {self.caused_by!r} does not match SSD-<AREA>-<NNN>")
        if not self.summary.strip():
            raise ValueError(f"finding {self.id} has an empty summary")


class FailureKind(StrEnum):
    """Why a probe produced no usable facts."""

    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    NONZERO_EXIT = "nonzero_exit"
    MALFORMED_OUTPUT = "malformed_output"
    OS_ERROR = "os_error"
    PROBE_ERROR = "probe_error"
    """The probe ran, but reported that part of its own work failed."""


@dataclass(frozen=True, slots=True)
class ProbeFailure:
    """A probe that could not deliver its facts.

    Collectors return these instead of raising, so one broken tool never hides the
    results of the others, and rules can report ``unknown`` with the reason.
    """

    probe: str
    kind: FailureKind
    detail: str


def utc_timestamp() -> str:
    """Current time as an ISO 8601 UTC string with second precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class SessionEnvironment:
    """The allowlisted session variables of the tool's own process; ``None`` means unset.

    Only these variables are read: the rest of the environment can hold tokens and
    passwords. Values are kept as they were found (``ubuntu:GNOME``, not ``gnome``), so a
    report shows what the portal saw. ``dbus_session_bus_address`` loses its ``guid=``
    part, and the SSH variables are reduced to ``ssh``: whether any of them is set.
    """

    session_type: str | None = None
    current_desktop: str | None = None
    session_desktop: str | None = None
    desktop_session: str | None = None
    wayland_display: str | None = None
    display: str | None = None
    runtime_dir: str | None = None
    session_id: str | None = None
    dbus_session_bus_address: str | None = None
    ssh: bool = False


class PathState(StrEnum):
    """What was found at a path the session depends on."""

    SOCKET = "socket"
    DIRECTORY = "directory"
    OTHER = "other"
    """Something exists, but not the kind of file expected there."""
    MISSING = "missing"
    UNREADABLE = "unreadable"
    NOT_CHECKED = "not_checked"
    """The path could not be worked out, e.g. ``WAYLAND_DISPLAY`` is unset."""


@dataclass(frozen=True, slots=True)
class SessionPaths:
    """The runtime directory and display sockets the session variables point to."""

    runtime_dir: PathState = PathState.NOT_CHECKED
    wayland_socket: PathState = PathState.NOT_CHECKED
    wayland_socket_path: str | None = None
    x11_socket: PathState = PathState.NOT_CHECKED
    x11_socket_path: str | None = None


@dataclass(frozen=True, slots=True)
class LogindSession:
    """What systemd-logind (or elogind) says about one session; ``None`` means not reported.

    ``session_type`` is logind's ``Type`` (``wayland``, ``x11``, ``tty``, ``mir``,
    ``unspecified``), ``session_class`` its ``Class`` (``user``, ``greeter``,
    ``manager``…).
    """

    id: str
    session_type: str | None = None
    session_class: str | None = None
    desktop: str | None = None
    remote: bool | None = None
    active: bool | None = None
    state: str | None = None
    seat: str | None = None


@dataclass(frozen=True, slots=True)
class LogindFacts:
    """The sessions logind reported for the user running the tool.

    ``own`` is the session named by ``XDG_SESSION_ID``. ``display`` is the user's
    graphical session (logind's ``Display``); it is the same session when the tool runs
    in a terminal of the desktop, and the only one known when it runs from the user
    manager. ``display_known`` is true when logind answered the question, so a ``None``
    ``display`` then means "no graphical session" rather than "not asked".
    """

    own: LogindSession | None = None
    display: LogindSession | None = None
    display_known: bool = False


@dataclass(frozen=True, slots=True)
class RedactionCount:
    """How many values of one kind (``home_path``, ``secret_value``…) were redacted."""

    kind: str
    count: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything one run observed and concluded; the input of every renderer.

    Session, portal and PipeWire facts join this record as their collectors are added.
    """

    tool_version: str
    created_at: str
    schema_version: int = SCHEMA_VERSION
    probe_failures: tuple[ProbeFailure, ...] = ()
    findings: tuple[Finding, ...] = ()
    redactions: tuple[RedactionCount, ...] = ()
