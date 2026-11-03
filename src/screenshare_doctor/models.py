"""Typed facts and findings shared by collectors, rules and renderers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
class SessionFacts:
    """Everything collected about the session: variables, paths and logind's view."""

    environment: SessionEnvironment = field(default_factory=SessionEnvironment)
    paths: SessionPaths = field(default_factory=SessionPaths)
    logind: LogindFacts = field(default_factory=LogindFacts)


class PackageState(StrEnum):
    """Whether a package is installed, as far as the package manager or the files tell."""

    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    BROKEN = "broken"
    """Half installed, unpacked but not configured, or flagged for reinstallation."""
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """One package of the screen-sharing stack; ``version`` as the package manager prints it."""

    name: str
    state: PackageState
    version: str | None = None


@dataclass(frozen=True, slots=True)
class PackageFacts:
    """The packages that were looked up and how.

    ``source`` is the package manager that answered (``dpkg``, ``rpm``, ``pacman``),
    ``files`` when only the installed programs could be looked for, or ``None`` when
    nothing was checked.
    """

    source: str | None = None
    packages: tuple[PackageInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class UserService:
    """One unit of the user's systemd manager, as ``systemctl --user show`` reports it.

    ``load_state``: ``loaded``, ``not-found``, ``masked``…; ``active_state``: ``active``,
    ``inactive``, ``failed``, ``activating``…; ``unit_file_state``: ``enabled``,
    ``static``, ``disabled``, ``masked``… ``None`` means systemd did not say.
    """

    unit: str
    load_state: str | None = None
    active_state: str | None = None
    sub_state: str | None = None
    unit_file_state: str | None = None


@dataclass(frozen=True, slots=True)
class XdgDirectories:
    """The variables that decide where the portal looks for its files; ``None`` = unset.

    They must be the portal process's own, which is the user manager's environment,
    not the shell's: Ubuntu's manager, for one, puts ``/usr/share/ubuntu`` first in
    ``XDG_DATA_DIRS``. ``portal_dir`` is ``XDG_DESKTOP_PORTAL_DIR``, a test override
    that replaces every other directory.
    """

    home: str | None = None
    config_home: str | None = None
    config_dirs: str | None = None
    data_home: str | None = None
    data_dirs: str | None = None
    portal_dir: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceFacts:
    """The user services of the stack, and the environment the user manager starts them in.

    Portals are started on demand by the user manager, so they see *its* environment,
    not the shell's: ``activation_environment`` holds the same allowlisted variables
    as the session environment, read from ``systemctl --user show-environment``, and
    ``activation_directories`` the variables that decide where portals look for their
    files. ``None`` fields were not read (no systemd, or the user manager did not answer).
    """

    services: tuple[UserService, ...] | None = None
    activation_environment: SessionEnvironment | None = None
    activation_directories: XdgDirectories | None = None


@dataclass(frozen=True, slots=True)
class BusName:
    """A well-known name on the session bus.

    ``running``: the name has an owner right now (``NameHasOwner``). ``activatable``: a
    D-Bus service file can start it on demand (``ListActivatableNames``). ``None`` means
    the bus was not asked or did not answer.
    """

    name: str
    running: bool | None = None
    activatable: bool | None = None


@dataclass(frozen=True, slots=True)
class ScreenCastProperties:
    """The ScreenCast interface's properties; ``None`` when not reported.

    ``source_types`` and ``cursor_modes`` are the bit masks from the specification:
    sources 1 monitor, 2 window, 4 virtual; cursor modes 1 hidden, 2 embedded,
    4 metadata.
    """

    version: int | None = None
    source_types: int | None = None
    cursor_modes: int | None = None


@dataclass(frozen=True, slots=True)
class PortalObject:
    """What a running portal service exposes.

    ``interfaces`` lists the portal interfaces it implements, from introspection
    (``None`` when it was not introspected). ``screencast`` holds its ScreenCast
    properties, ``None`` when it has no ScreenCast interface or they could not be read.
    """

    name: str
    interfaces: tuple[str, ...] | None = None
    screencast: ScreenCastProperties | None = None


@dataclass(frozen=True, slots=True)
class DbusFacts:
    """What the session bus said, read without starting any service.

    ``reachable`` is ``False`` when the session bus itself did not answer, ``None``
    when it was not tried. ``objects`` covers only names that were already running.
    """

    reachable: bool | None = None
    names: tuple[BusName, ...] = ()
    objects: tuple[PortalObject, ...] = ()


@dataclass(frozen=True, slots=True)
class PortalDescriptor:
    """A ``<source>.portal`` file: which backend implements which interfaces.

    ``source`` is the file name without ``.portal``; it is the name ``portals.conf``
    refers to. ``error`` says why the portal frontend would skip the file (unreadable,
    no valid ``DBusName``, an interface outside ``org.freedesktop.impl.portal.*``…);
    ``None`` means it is usable.
    """

    source: str
    path: str
    dbus_name: str | None = None
    interfaces: tuple[str, ...] = ()
    use_in: tuple[str, ...] | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PortalsConf:
    """One ``portals.conf`` or ``<desktop>-portals.conf`` file.

    ``preferred`` holds the ``[preferred]`` keys in file order with their backend lists
    (a key set twice keeps its last value; ``duplicates`` names such keys). ``usable``
    is ``False`` when the portal would ignore the file: unreadable, invalid, or without
    a ``[preferred]`` group; ``error`` then says why.
    """

    path: str
    preferred: tuple[tuple[str, tuple[str, ...]], ...] = ()
    duplicates: tuple[str, ...] = ()
    usable: bool = True
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PortalFiles:
    """The portal configuration as found on disk, in the frontend's search order.

    ``desktops`` are the names the lookup used (from the portal's
    ``XDG_CURRENT_DESKTOP``). ``configs`` are the candidate files that exist,
    highest priority first; ``descriptors`` every ``.portal`` file found, in load order
    (duplicates included: the first file of a name wins). ``unreadable`` lists files
    that exist but could not be read, so nothing is concluded from their absence.
    """

    desktops: tuple[str, ...] = ()
    config_directories: tuple[str, ...] = ()
    configs: tuple[PortalsConf, ...] = ()
    descriptor_directories: tuple[str, ...] = ()
    descriptors: tuple[PortalDescriptor, ...] = ()
    unreadable: tuple[str, ...] = ()
    variables_from: str = "user manager"
    """Whose ``XDG_CURRENT_DESKTOP`` and directory variables were used: the ``user
    manager`` (the portal's own) or, when it could not be asked, ``this shell``."""


@dataclass(frozen=True, slots=True)
class PipeWireFacts:
    """What the PipeWire daemon reported, reduced to what screen sharing needs.

    ``skipped`` says why PipeWire was not asked (connecting to a socket-activated
    daemon that is not running would start it); the other fields are then ``None``.
    ``clients`` are the connected clients whose names matter here (WirePlumber, the
    portal, the compositor); any other client is only counted in ``other_clients``,
    because application names say what the user is doing. ``camera_sources`` are
    ``Video/Source`` nodes of a camera API (v4l2, libcamera); ``other_video_sources``
    are the rest, such as a running screen cast.
    """

    skipped: str | None = None
    version: str | None = None
    clients: tuple[str, ...] | None = None
    other_clients: int | None = None
    camera_sources: int | None = None
    other_video_sources: int | None = None
    video_streams: int | None = None


@dataclass(frozen=True, slots=True)
class RedactionCount:
    """How many values of one kind (``home_path``, ``secret_value``…) were redacted."""

    kind: str
    count: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything one run observed and concluded; the input of every renderer.

    ``session``, ``packages``, ``services``, ``dbus`` and ``portal_files`` are ``None``
    when the command did not look at them. PipeWire facts join this record as their
    collector is added.
    """

    tool_version: str
    created_at: str
    schema_version: int = SCHEMA_VERSION
    session: SessionFacts | None = None
    packages: PackageFacts | None = None
    services: ServiceFacts | None = None
    dbus: DbusFacts | None = None
    portal_files: PortalFiles | None = None
    probe_failures: tuple[ProbeFailure, ...] = ()
    findings: tuple[Finding, ...] = ()
    redactions: tuple[RedactionCount, ...] = ()
