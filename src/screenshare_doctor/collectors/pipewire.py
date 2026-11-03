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
