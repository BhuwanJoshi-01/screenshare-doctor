"""Which backend the portal frontend picks for an interface, and why.

A pure re-implementation of the selection in xdg-desktop-portal
(``desktop-portal/xdp-portal-config.c``, formerly ``src/portal-impl.c``). The rules
changed between releases, and the differences decide real cases, so each behaviour
is modelled from that release's source:

- before 1.17: no ``portals.conf``; only the descriptors' ``UseIn`` key, then gtk;
- 1.17 and 1.18: the first configuration file found is used, but its lists are not
  read in order: the first installed backend (sorted by ``UseIn``, then name) that the
  list names wins. An interface entry replaces ``default`` entirely;
- 1.19 to 1.21.0: lists are read in order; an interface entry that finds nothing falls
  back to ``default``. ``default=*`` finds nothing (the lookup used the key name
  ``default`` as the interface), so the ``UseIn`` and gtk fallbacks decide;
- from 1.20.1 descriptors are also read from the user and ``XDG_DATA_DIRS`` data
  directories, not only ``/usr/share``;
- from 1.21.1 every directory's configuration is consulted in order until one names a
  usable backend, and ``default=*`` works.

The result is a prediction with its reasoning; whether that backend really answers is
a separate, observed fact (see the D-Bus collector).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from screenshare_doctor.collectors.dbus import FRONTEND
from screenshare_doctor.desktops import ascii_lower
from screenshare_doctor.models import DbusFacts, PortalDescriptor, PortalFiles, PortalsConf
from screenshare_doctor.portal_paths import DATADIR, SUBDIR, config_candidates, join

GTK_BUS_NAME = "org.freedesktop.impl.portal.desktop.gtk"
NEWEST = (1, 21, 1)
"""The newest behaviour; assumed when the frontend's version is unknown."""

_VERSION = re.compile(r"(?:\d+:)?(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True, slots=True)
class PortalBehaviour:
    """The selection rules of one xdg-desktop-portal release."""

    version: tuple[int, int, int] | None

    @property
    def effective(self) -> tuple[int, int, int]:
        return self.version or NEWEST

    @property
    def reads_config(self) -> bool:
        return self.effective >= (1, 17, 0)

    @property
    def ordered_lists(self) -> bool:
        return self.effective >= (1, 19, 0)

    @property
    def all_descriptor_dirs(self) -> bool:
        return self.effective >= (1, 20, 1)

    @property
    def falls_through(self) -> bool:
        """Every directory's config is consulted, and ``default=*`` works."""
        return self.effective >= (1, 21, 1)


def parse_portal_version(package_version: str | None) -> tuple[int, int, int] | None:
    """``(1, 21, 1)`` from ``1.21.1+ds-1ubuntu3.1``, ``1:1.20.3-1`` or ``1.18``."""
    if not package_version:
        return None
    match = _VERSION.match(package_version.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


class RouteKind(StrEnum):
    BACKEND = "backend"
    DISABLED = "disabled"
    """A configuration says ``none`` for this interface."""
    NOTHING = "nothing"
    """No backend qualifies: the interface is not offered."""


class Rule(StrEnum):
    """What decided the route."""

    INTERFACE = "interface"
    DEFAULT = "default"
    NONE = "none"
    USE_IN = "use_in"
    GTK_FALLBACK = "gtk_fallback"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class Route:
    """The predicted backend for one interface and the reasoning behind it.

    ``config`` is the file that decided (``None`` for the fallbacks); ``trace`` the
    steps in the frontend's order; ``uncertain`` reasons the prediction may be wrong
    (an unreadable file, an unknown portal version).
    """

    interface: str
    kind: RouteKind
    rule: Rule
    backend: PortalDescriptor | None = None
    config: str | None = None
    trace: tuple[str, ...] = ()
    uncertain: tuple[str, ...] = ()


def installed_backends(
    files: PortalFiles, behaviour: PortalBehaviour, trace: list[str]
) -> list[PortalDescriptor]:
    """The descriptors the frontend loads, in its preference order (``UseIn``, then name)."""
    system_dir = join(DATADIR, SUBDIR, "portals")
    # Before 1.20.1 only /usr/share/xdg-desktop-portal/portals was read (or the
    # XDG_DESKTOP_PORTAL_DIR override, which is then the only directory listed).
    only_system = not behaviour.all_descriptor_dirs and len(files.descriptor_directories) > 1
    loaded: dict[str, PortalDescriptor] = {}
    for descriptor in files.descriptors:
        directory = descriptor.path.rsplit("/", 1)[0]
        if only_system and directory != system_dir:
            trace.append(f"not read by this portal version: {descriptor.path}")
            continue
        if descriptor.error is not None:
            trace.append(f"skipped {descriptor.path}: {descriptor.error}")
            continue
        if descriptor.source in loaded:
            if loaded[descriptor.source].path != descriptor.path:
                trace.append(
                    f"ignored {descriptor.path}: {loaded[descriptor.source].path} was loaded first"
                )
            continue
        loaded[descriptor.source] = descriptor
    desktops = files.desktops

    def rank(descriptor: PortalDescriptor) -> tuple[int, str]:
        use_in = {ascii_lower(name) for name in descriptor.use_in or ()}
        for index, desktop in enumerate(desktops):
            if ascii_lower(desktop) in use_in:
                return (index, descriptor.source)
        return (len(desktops), descriptor.source)

    return sorted(loaded.values(), key=rank)


def chosen_configs(
    files: PortalFiles, behaviour: PortalBehaviour, trace: list[str], uncertain: list[str]
) -> list[PortalsConf]:
    """The configuration of each search directory, in order; only the first one before
    1.21.1. In a directory, ``<desktop>-portals.conf`` is tried for each desktop name,
    then ``portals.conf``; the first that loads is that directory's configuration."""
    if not behaviour.reads_config:
        trace.append("portals.conf is not read by this portal version (before 1.17)")
        return []
    by_path = {conf.path: conf for conf in files.configs}
    unreadable = set(files.unreadable)
    chosen: list[PortalsConf] = []
    for directory in files.config_directories:
        for path in config_candidates(directory, files.desktops):
            if path in unreadable:
                uncertain.append(f"{path} exists but could not be read")
                continue
            conf = by_path.get(path)
            if conf is None:
                continue
            if not conf.usable:
                trace.append(f"ignored {path}: {conf.error}")
                continue
            chosen.append(conf)
            break
        if chosen and not behaviour.falls_through:
            break
    if not chosen:
        trace.append("no usable portals.conf was found")
    return chosen


def resolve_route(interface: str, files: PortalFiles, behaviour: PortalBehaviour) -> Route:
    """Predict the backend the frontend uses for ``interface`` (an ``impl`` interface)."""
    trace: list[str] = []
    uncertain: list[str] = []
    if behaviour.version is None:
        uncertain.append("the portal version is unknown; the newest rules were applied")
    backends = installed_backends(files, behaviour, trace)
    configs = chosen_configs(files, behaviour, trace, uncertain)

    def route(
        kind: RouteKind,
        rule: Rule,
        backend: PortalDescriptor | None = None,
        config: str | None = None,
    ) -> Route:
        return Route(interface, kind, rule, backend, config, tuple(trace), tuple(uncertain))

    for conf in configs:
        entries = dict(conf.preferred)
        own = entries.get(interface)
        default = entries.get("default")
        if (own is not None and "none" in own) or (
            own is None and default is not None and "none" in default
        ):
            key = interface if own is not None else "default"
            trace.append(f"{conf.path}: {key} contains none")
            return route(RouteKind.DISABLED, Rule.NONE, config=conf.path)
        if behaviour.ordered_lists:
            if own is not None:
                found = _first_listed(own, interface, interface, backends, trace, conf.path)
                if found is not None:
                    return route(RouteKind.BACKEND, Rule.INTERFACE, found, conf.path)
            if default is not None:
                star_target = interface if behaviour.falls_through else "default"
                found = _first_listed(default, interface, star_target, backends, trace, conf.path)
                if found is not None:
                    return route(RouteKind.BACKEND, Rule.DEFAULT, found, conf.path)
        else:
            entry, rule = (own, Rule.INTERFACE) if own is not None else (default, Rule.DEFAULT)
            if entry is not None:
                for backend in backends:
                    if interface in backend.interfaces and (
                        backend.source in entry or "*" in entry
                    ):
                        trace.append(
                            f"{conf.path}: {backend.source} is the first installed backend "
                            "the list allows (this portal version ignores the list order)"
                        )
                        return route(RouteKind.BACKEND, rule, backend, conf.path)
        trace.append(f"{conf.path}: names no installed backend that implements {interface}")

    for desktop in files.desktops:
        for backend in backends:
            use_in = {ascii_lower(name) for name in backend.use_in or ()}
            if interface in backend.interfaces and ascii_lower(desktop) in use_in:
                trace.append(f"{backend.path}: UseIn={desktop} (deprecated fallback)")
                return route(RouteKind.BACKEND, Rule.USE_IN, backend)
    for backend in backends:
        if backend.dbus_name == GTK_BUS_NAME and interface in backend.interfaces:
            trace.append(f"{backend.path}: the gtk backend is the last-resort fallback")
            return route(RouteKind.BACKEND, Rule.GTK_FALLBACK, backend)
    trace.append(f"no installed backend implements {interface}")
    return route(RouteKind.NOTHING, Rule.NO_MATCH)


def _first_listed(
    names: tuple[str, ...],
    interface: str,
    star_target: str,
    backends: list[PortalDescriptor],
    trace: list[str],
    path: str,
) -> PortalDescriptor | None:
    """The first listed backend that is installed and implements ``interface``.

    ``*`` ends the search either way: it means the first installed backend (in
    preference order) that implements ``star_target``.
    """
    by_source = {backend.source: backend for backend in backends}
    for name in names:
        if name == "*":
            for backend in backends:
                if star_target in backend.interfaces:
                    trace.append(f"{path}: * picks {backend.source}, the first that implements it")
                    return backend
            trace.append(f"{path}: * matched nothing")
            return None
        candidate = by_source.get(name)
        if candidate is None:
            trace.append(f"{path}: {name} is listed but not installed")
            continue
        if interface not in candidate.interfaces:
            trace.append(f"{path}: {name} does not implement {interface}")
            continue
        trace.append(f"{path}: {name} is listed and implements {interface}")
        return candidate
    return None


class Agreement(StrEnum):
    """How the predicted route compares with what is on the session bus."""

    CONSISTENT = "consistent"
    """The predicted backend runs and implements the interface, and the frontend offers it."""
    STARTS_ON_DEMAND = "starts_on_demand"
    """The backend is not running but the bus can start it: normal for portals."""
    CANNOT_START = "cannot_start"
    """The backend is neither running nor activatable: requests will fail."""
    MISSING_INTERFACE = "missing_interface"
    """The running backend does not implement the interface its descriptor promises."""
    NOT_OFFERED = "not_offered"
    """The frontend does not offer the public interface although a backend was predicted."""
    OFFERED_WITHOUT_BACKEND = "offered_without_backend"
    """The frontend offers the interface although no backend was predicted."""
    NOT_CHECKED = "not_checked"
    """The backend's bus name is not one the tool probes, or the bus was not reachable."""


@dataclass(frozen=True, slots=True)
class RouteObservation:
    """The predicted route next to the bus facts it can be checked against."""

    agreement: Agreement
    backend_running: bool | None = None
    backend_activatable: bool | None = None
    backend_implements: bool | None = None
    frontend_offers: bool | None = None


def public_interface(impl_interface: str) -> str:
    """``org.freedesktop.portal.ScreenCast`` for ``org.freedesktop.impl.portal.ScreenCast``."""
    return impl_interface.replace(".impl.portal.", ".portal.", 1)


def observe_route(route: Route, dbus: DbusFacts | None) -> RouteObservation:
    """Compare a prediction with the bus: configured is not the same as working."""
    if dbus is None or dbus.reachable is not True:
        return RouteObservation(Agreement.NOT_CHECKED)
    objects = {portal.name: portal for portal in dbus.objects}
    frontend = objects.get(FRONTEND)
    offers: bool | None = None
    if frontend is not None and frontend.interfaces is not None:
        offers = public_interface(route.interface) in frontend.interfaces
    if route.backend is None:
        if offers:
            return RouteObservation(Agreement.OFFERED_WITHOUT_BACKEND, frontend_offers=True)
        return RouteObservation(Agreement.CONSISTENT, frontend_offers=offers)
    names = {name.name: name for name in dbus.names}
    bus_name = names.get(route.backend.dbus_name or "")
    if bus_name is None:
        return RouteObservation(Agreement.NOT_CHECKED, frontend_offers=offers)
    implements: bool | None = None
    backend_object = objects.get(bus_name.name)
    if backend_object is not None and backend_object.interfaces is not None:
        implements = route.interface in backend_object.interfaces
    facts = {
        "backend_running": bus_name.running,
        "backend_activatable": bus_name.activatable,
        "backend_implements": implements,
        "frontend_offers": offers,
    }
    if bus_name.running is False:
        if bus_name.activatable:
            return RouteObservation(Agreement.STARTS_ON_DEMAND, **facts)
        if bus_name.activatable is False:
            return RouteObservation(Agreement.CANNOT_START, **facts)
    if implements is False:
        return RouteObservation(Agreement.MISSING_INTERFACE, **facts)
    if offers is False and bus_name.running:
        return RouteObservation(Agreement.NOT_OFFERED, **facts)
    if bus_name.running and implements and offers is not False:
        return RouteObservation(Agreement.CONSISTENT, **facts)
    return RouteObservation(Agreement.NOT_CHECKED, **facts)


_SHORT_INTERFACE = re.compile(r"[A-Za-z][A-Za-z0-9]*", re.ASCII)


def normalize_interface(name: str) -> str | None:
    """The backend interface for ``ScreenCast``, ``org.freedesktop.portal.ScreenCast`` or
    ``org.freedesktop.impl.portal.ScreenCast``; ``None`` for anything else."""
    for prefix in ("org.freedesktop.impl.portal.", "org.freedesktop.portal."):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    if not _SHORT_INTERFACE.fullmatch(name):
        return None
    return f"org.freedesktop.impl.portal.{name}"
