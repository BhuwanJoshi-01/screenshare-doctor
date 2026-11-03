"""Desktop rule bundles: what each desktop ships for screen sharing, with sources.

The data lives in ``desktops.json`` so it can be reviewed and corrected without
reading code. Every claim names the file or repository it comes from and when it was
read. A bundle is an expectation to compare with, never a verdict: a different backend
can be a perfectly valid choice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from screenshare_doctor.desktops import DesktopFamily


@dataclass(frozen=True, slots=True)
class Source:
    claim: str
    url: str
    retrieved: str


@dataclass(frozen=True, slots=True)
class DesktopBundle:
    """The screen-sharing setup a desktop ships; ``None`` fields have no expectation.

    ``config_file`` is the ``portals.conf`` the desktop installs into
    ``/usr/share/xdg-desktop-portal`` (``config_shipped_by`` says which package does).
    ``compositor_bus_name`` is a session-bus service the backend depends on.
    """

    family: DesktopFamily
    name: str
    backend: str
    backend_bus_name: str
    backend_package: str
    backend_unit: str
    config_file: str | None
    config_shipped_by: str | None
    config_default: tuple[str, ...]
    compositor_bus_name: str | None
    sources: tuple[Source, ...]


class BundleDataError(ValueError):
    """desktops.json does not have the documented shape."""


def _bundle(raw: dict[str, Any]) -> DesktopBundle:
    try:
        return DesktopBundle(
            family=DesktopFamily(raw["family"]),
            name=str(raw["name"]),
            backend=str(raw["backend"]),
            backend_bus_name=str(raw["backend_bus_name"]),
            backend_package=str(raw["backend_package"]),
            backend_unit=str(raw["backend_unit"]),
            config_file=raw["config_file"],
            config_shipped_by=raw["config_shipped_by"],
            config_default=tuple(raw["config_default"]),
            compositor_bus_name=raw["compositor_bus_name"],
            sources=tuple(Source(s["claim"], s["url"], s["retrieved"]) for s in raw["sources"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BundleDataError(f"invalid desktop bundle: {exc}") from None


def parse_bundles(text: str) -> dict[DesktopFamily, DesktopBundle]:
    data = json.loads(text)
    bundles = [_bundle(raw) for raw in data["desktops"]]
    return {bundle.family: bundle for bundle in bundles}


@cache
def load_bundles() -> dict[DesktopFamily, DesktopBundle]:
    """The bundles shipped with the tool, by desktop family."""
    text = resources.files(__package__).joinpath("desktops.json").read_text(encoding="utf-8")
    return parse_bundles(text)


def bundle_for(family: DesktopFamily) -> DesktopBundle | None:
    return load_bundles().get(family)
