"""Configured versus observed (WLD-005)."""

from __future__ import annotations

from screenshare_doctor.collectors.dbus import FRONTEND, collect_dbus
from screenshare_doctor.models import BusName, DbusFacts, PortalDescriptor, PortalObject
from screenshare_doctor.routes import (
    Agreement,
    Route,
    RouteKind,
    Rule,
    observe_route,
    public_interface,
)
from tests.fakes import FakeRunner
from tests.scenarios import script_gnome_bus

SC = "org.freedesktop.impl.portal.ScreenCast"
GNOME_BUS = "org.freedesktop.impl.portal.desktop.gnome"
KDE_BUS = "org.freedesktop.impl.portal.desktop.kde"


def _route(bus: str | None, source: str = "gnome") -> Route:
    if bus is None:
        return Route(SC, RouteKind.NOTHING, Rule.NO_MATCH)
    backend = PortalDescriptor(
        source, f"/usr/share/xdg-desktop-portal/portals/{source}.portal", bus, (SC,)
    )
    return Route(SC, RouteKind.BACKEND, Rule.DEFAULT, backend)


def _real_bus() -> DbusFacts:
    runner = FakeRunner()
    script_gnome_bus(runner)
    return collect_dbus(runner)[0]


def test_real_gnome_session_is_consistent() -> None:
    observation = observe_route(_route(GNOME_BUS), _real_bus())
    assert observation.agreement is Agreement.CONSISTENT
    assert observation.backend_running is True
    assert observation.backend_implements is True
    assert observation.frontend_offers is True


def test_predicted_backend_that_cannot_start() -> None:
    observation = observe_route(_route(KDE_BUS, "kde"), _real_bus())
    assert observation.agreement is Agreement.CANNOT_START
    assert (observation.backend_running, observation.backend_activatable) == (False, False)


def test_stopped_but_activatable_backend_is_normal() -> None:
    dbus = DbusFacts(True, (BusName(GNOME_BUS, running=False, activatable=True),))
    assert observe_route(_route(GNOME_BUS), dbus).agreement is Agreement.STARTS_ON_DEMAND


def test_running_backend_without_the_interface() -> None:
    dbus = DbusFacts(
        True,
        (BusName(GNOME_BUS, running=True, activatable=True),),
        (PortalObject(GNOME_BUS, ("org.freedesktop.impl.portal.FileChooser",)),),
    )
    assert observe_route(_route(GNOME_BUS), dbus).agreement is Agreement.MISSING_INTERFACE


def test_frontend_that_does_not_offer_the_interface() -> None:
    dbus = DbusFacts(
        True,
        (BusName(FRONTEND, True, True), BusName(GNOME_BUS, True, True)),
        (
            PortalObject(FRONTEND, ("org.freedesktop.portal.FileChooser",)),
            PortalObject(GNOME_BUS, (SC,)),
        ),
    )
    assert observe_route(_route(GNOME_BUS), dbus).agreement is Agreement.NOT_OFFERED


def test_no_backend_predicted_but_the_frontend_offers_one() -> None:
    dbus = DbusFacts(
        True,
        (BusName(FRONTEND, True, True),),
        (PortalObject(FRONTEND, (public_interface(SC),)),),
    )
    assert observe_route(_route(None), dbus).agreement is Agreement.OFFERED_WITHOUT_BACKEND


def test_no_backend_and_nothing_offered_agree() -> None:
    dbus = DbusFacts(True, (BusName(FRONTEND, True, True),), (PortalObject(FRONTEND, ()),))
    assert observe_route(_route(None), dbus).agreement is Agreement.CONSISTENT


def test_unprobed_bus_name_is_not_checked() -> None:
    route = _route("org.freedesktop.impl.portal.desktop.cosmic", "cosmic")
    assert observe_route(route, _real_bus()).agreement is Agreement.NOT_CHECKED


def test_unreachable_bus_is_not_checked() -> None:
    assert (
        observe_route(_route(GNOME_BUS), DbusFacts(reachable=False)).agreement
        is Agreement.NOT_CHECKED
    )
    assert observe_route(_route(GNOME_BUS), None).agreement is Agreement.NOT_CHECKED


def test_public_interface_name() -> None:
    assert public_interface(SC) == "org.freedesktop.portal.ScreenCast"
