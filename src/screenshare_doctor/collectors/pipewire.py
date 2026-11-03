"""The PipeWire daemon, asked with ``pw-dump`` and reduced to counters at once.

Screen sharing ends in PipeWire: the portal backend asks the compositor for a video
stream and hands the app a PipeWire node. Whether the daemon answers, whether the
session manager (WirePlumber) is connected and whether the portal itself is a client
tell which link is missing. Everything else in a dump (application names, media
titles, device names) is dropped while parsing.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from screenshare_doctor.models import FailureKind, PipeWireFacts, ProbeFailure, ServiceFacts
from screenshare_doctor.runner import CommandRunner, probe_failure

KNOWN_CLIENTS: tuple[str, ...] = (
    "WirePlumber",
    "xdg-desktop-portal",
    "gnome-shell",
    "Mutter",
    "kwin_wayland",
    "xdg-desktop-portal-gnome",
    "xdg-desktop-portal-kde",
    "xdg-desktop-portal-wlr",
    "xdg-desktop-portal-hyprland",
)
"""Clients named in reports; any other application is only counted."""

_IGNORED_CLIENTS = ("pipewire", "pw-dump", "WirePlumber [export]")
"""The daemon itself, this probe, and WirePlumber's second connection."""

CAMERA_APIS = ("v4l2", "libcamera")


class PwDumpError(ValueError):
    """pw-dump printed something that is not the JSON array it promises."""


def parse_pw_dump(text: str) -> list[dict[str, Any]]:
    try:
        objects = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PwDumpError(f"not JSON: {exc.msg}") from None
    if not isinstance(objects, list) or not all(isinstance(o, dict) for o in objects):
        raise PwDumpError("not a list of objects")
    return objects


def _props(obj: dict[str, Any]) -> dict[str, Any]:
    info = obj.get("info")
    props = info.get("props") if isinstance(info, dict) else None
    return props if isinstance(props, dict) else {}


def core_version(objects: list[dict[str, Any]]) -> str | None:
    for obj in objects:
        if obj.get("type") == "PipeWire:Interface:Core":
            info = obj.get("info")
            version = info.get("version") if isinstance(info, dict) else None
            return version if isinstance(version, str) else None
    return None


def client_summary(objects: list[dict[str, Any]]) -> tuple[tuple[str, ...], int]:
    """Known client names (sorted, unique) and the number of other clients."""
    known: set[str] = set()
    others = 0
    for obj in objects:
        if obj.get("type") != "PipeWire:Interface:Client":
            continue
        name = _props(obj).get("application.name")
        if name in _IGNORED_CLIENTS:
            continue
        if name in KNOWN_CLIENTS:
            known.add(name)
        else:
            others += 1
    return tuple(sorted(known)), others


def video_summary(objects: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Camera sources, other video sources and video streams among the nodes."""
    counts: Counter[str] = Counter()
    for obj in objects:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = _props(obj)
        media_class = props.get("media.class")
        if media_class == "Video/Source":
            counts["camera" if props.get("device.api") in CAMERA_APIS else "other"] += 1
        elif media_class in ("Stream/Output/Video", "Stream/Input/Video"):
            counts["stream"] += 1
    return counts["camera"], counts["other"], counts["stream"]


PW_DUMP_TIMEOUT = 5.0
OBJECT_TYPES = ("PipeWire:Interface:Core", "PipeWire:Interface:Client", "PipeWire:Interface:Node")
"""Dumped one type at a time: a whole dump of a busy session exceeds the output cap."""


def may_connect(services: ServiceFacts | None, *, systemd_missing: bool) -> str | None:
    """``None`` when connecting to PipeWire cannot start it, otherwise the reason not to.

    With systemd, ``pipewire.socket`` starts the daemon on the first connection, so a
    probe of a stopped daemon would start it. Only an active ``pipewire.service`` is
    asked. Without systemd there is no socket activation, so connecting is harmless.
    """
    if services is None or services.services is None:
        if systemd_missing:
            return None
        return "the state of pipewire.service is unknown; not connecting, so as not to start it"
    for service in services.services:
        if service.unit == "pipewire.service":
            if service.active_state == "active":
                return None
            state = service.active_state or "unknown"
            return f"pipewire.service is not running ({state}); connecting would start it"
    return "pipewire.service was not checked; not connecting, so as not to start it"


def collect_pipewire(
    runner: CommandRunner, services: ServiceFacts | None, *, systemd_missing: bool = False
) -> tuple[PipeWireFacts, tuple[ProbeFailure, ...]]:
    """Ask a running PipeWire daemon for its version, known clients and video nodes."""
    reason = may_connect(services, systemd_missing=systemd_missing)
    if reason is not None:
        return PipeWireFacts(skipped=reason), ()
    dumps: dict[str, list[dict[str, Any]]] = {}
    for object_type in OBJECT_TYPES:
        result = runner.run(["pw-dump", "-N", "-i", "0", object_type], timeout=PW_DUMP_TIMEOUT)
        failure = probe_failure("pw-dump", result)
        if failure is None and result.stdout_truncated:
            failure = ProbeFailure("pw-dump", FailureKind.MALFORMED_OUTPUT, "output was truncated")
        if failure is None:
            try:
                dumps[object_type] = parse_pw_dump(result.stdout)
            except PwDumpError as exc:
                failure = ProbeFailure("pw-dump", FailureKind.MALFORMED_OUTPUT, str(exc))
        if failure is not None:
            return PipeWireFacts(), (failure,)
    known, others = client_summary(dumps["PipeWire:Interface:Client"])
    cameras, other_sources, streams = video_summary(dumps["PipeWire:Interface:Node"])
    return (
        PipeWireFacts(
            version=core_version(dumps["PipeWire:Interface:Core"]),
            clients=known,
            other_clients=others,
            camera_sources=cameras,
            other_video_sources=other_sources,
            video_streams=streams,
        ),
        (),
    )
