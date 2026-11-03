"""The shipped desktop bundles are complete and sourced (WLD-007)."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest

from screenshare_doctor.bundles import BundleDataError, bundle_for, load_bundles, parse_bundles
from screenshare_doctor.collectors.dbus import BUS_NAMES
from screenshare_doctor.collectors.packages import PACKAGES
from screenshare_doctor.collectors.services import UNITS
from screenshare_doctor.desktops import DesktopFamily
from screenshare_doctor.portal_files import is_bus_name


def test_the_three_target_desktops_and_wlroots_have_bundles() -> None:
    assert set(load_bundles()) == {
        DesktopFamily.GNOME,
        DesktopFamily.KDE,
        DesktopFamily.HYPRLAND,
        DesktopFamily.WLROOTS,
    }
    assert bundle_for(DesktopFamily.OTHER) is None


@pytest.mark.parametrize("family", list(load_bundles()))
def test_every_bundle_is_sourced_and_consistent(family: DesktopFamily) -> None:
    bundle = load_bundles()[family]
    assert bundle.sources
    for source in bundle.sources:
        assert source.url.startswith("https://")
        assert date.fromisoformat(source.retrieved) <= date(2026, 11, 3)
        assert source.claim
    assert is_bus_name(bundle.backend_bus_name)
    assert bundle.backend_bus_name.endswith(f".desktop.{bundle.backend}")
    # The collectors must look at what the bundles expect.
    assert bundle.backend_package in PACKAGES
    assert bundle.backend_unit in UNITS
    assert bundle.backend_bus_name in BUS_NAMES
    if bundle.compositor_bus_name is not None:
        assert bundle.compositor_bus_name in BUS_NAMES
    if bundle.config_file is not None:
        assert re.fullmatch(r"[a-z0-9_-]+-portals\.conf", bundle.config_file)
        assert bundle.config_default[0] == bundle.backend


def test_malformed_data_is_rejected() -> None:
    with pytest.raises(BundleDataError):
        parse_bundles(json.dumps({"desktops": [{"family": "gnome"}]}))
    with pytest.raises(BundleDataError):
        parse_bundles(json.dumps({"desktops": [{"family": "unknown-family", "name": "x"}]}))
