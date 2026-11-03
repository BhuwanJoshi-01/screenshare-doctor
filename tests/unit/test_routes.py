"""Predicting the portal backend for an interface (WLD-005)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.models import PortalDescriptor, PortalFiles, PortalsConf, XdgDirectories
from screenshare_doctor.portal_files import parse_descriptor, parse_portals_conf
from screenshare_doctor.portal_paths import config_directories, descriptor_directories
from screenshare_doctor.routes import (
    PortalBehaviour,
    RouteKind,
    Rule,
    parse_portal_version,
    resolve_route,
)
from tests.fakes import FIXTURES

SC = "org.freedesktop.impl.portal.ScreenCast"
FC = "org.freedesktop.impl.portal.FileChooser"
DIRS = XdgDirectories(home="/home/u")
SYSTEM = "/usr/share/xdg-desktop-portal"
USER_CONFIG = "/home/u/.config/xdg-desktop-portal"
NEW = PortalBehaviour((1, 21, 1))
V120 = PortalBehaviour((1, 20, 3))
V119 = PortalBehaviour((1, 19, 0))
V118 = PortalBehaviour((1, 18, 4))
V116 = PortalBehaviour((1, 16, 0))


def desc(
    source: str,
    *interfaces: str,
    use_in: tuple[str, ...] | None = None,
    directory: str = f"{SYSTEM}/portals",
    bus: str | None = None,
) -> PortalDescriptor:
    return PortalDescriptor(
        source,
        f"{directory}/{source}.portal",
        bus or f"org.freedesktop.impl.portal.desktop.{source}",
        interfaces,
        use_in,
    )


def conf(path: str, *entries: tuple[str, tuple[str, ...]]) -> PortalsConf:
    return PortalsConf(path, entries)


def files(
    desktops: tuple[str, ...],
    descriptors: tuple[PortalDescriptor, ...],
    configs: tuple[PortalsConf, ...] = (),
    unreadable: tuple[str, ...] = (),
    dirs: XdgDirectories = DIRS,
) -> PortalFiles:
    return PortalFiles(
        desktops=desktops,
        config_directories=config_directories(dirs),
        configs=configs,
        descriptor_directories=descriptor_directories(dirs),
        descriptors=descriptors,
        unreadable=unreadable,
    )


GNOME = desc("gnome", SC, FC, use_in=("gnome",))
GTK = desc("gtk", FC, use_in=("gnome",), bus="org.freedesktop.impl.portal.desktop.gtk")
KDE = desc("kde", SC, FC, use_in=("KDE",))
WLR = desc("wlr", SC, use_in=("sway", "wlroots"))
HYPRLAND = desc("hyprland", SC, use_in=("hyprland",))


def test_real_ubuntu_gnome_configuration() -> None:
    portal_files = files(
        ("ubuntu", "gnome"),
        tuple(
            parse_descriptor(f"{SYSTEM}/portals/{name}", (FIXTURES / "portals" / name).read_bytes())
            for name in ("gnome-keyring.portal", "gnome.portal", "gtk.portal")
        ),
        (
            parse_portals_conf(
                f"{SYSTEM}/gnome-portals.conf",
                (FIXTURES / "portals" / "gnome-portals.conf").read_bytes(),
            ),
        ),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert (route.kind, route.rule) == (RouteKind.BACKEND, Rule.DEFAULT)
    assert route.backend is not None
    assert route.backend.source == "gnome"
    assert route.config == f"{SYSTEM}/gnome-portals.conf"
    assert route.uncertain == ()
    inhibit = resolve_route("org.freedesktop.impl.portal.Inhibit", portal_files, NEW)
    assert inhibit.backend is not None
    assert inhibit.backend.source == "gtk"  # gnome lacks Inhibit, gtk is next in default
    secret = resolve_route("org.freedesktop.impl.portal.Secret", portal_files, NEW)
    assert (secret.rule, secret.backend.source if secret.backend else None) == (
        Rule.INTERFACE,
        "gnome-keyring",
    )


def test_interface_entry_beats_default() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME, WLR),
        (conf(f"{SYSTEM}/gnome-portals.conf", ("default", ("gnome",)), (SC, ("wlr",))),),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert route.backend == WLR
    assert route.rule is Rule.INTERFACE


def test_user_configuration_comes_first() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME, WLR),
        (
            conf(f"{USER_CONFIG}/portals.conf", ("default", ("wlr",))),
            conf(f"{SYSTEM}/gnome-portals.conf", ("default", ("gnome",))),
        ),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert route.backend == WLR
    assert route.config == f"{USER_CONFIG}/portals.conf"


def test_desktop_file_beats_portals_conf_in_the_same_directory() -> None:
    portal_files = files(
        ("hyprland",),
        (HYPRLAND, GNOME),
        (
            conf(f"{USER_CONFIG}/hyprland-portals.conf", ("default", ("hyprland",))),
            conf(f"{USER_CONFIG}/portals.conf", ("default", ("gnome",))),
        ),
    )
    assert resolve_route(SC, portal_files, NEW).backend == HYPRLAND


def test_unusable_file_falls_to_the_next_candidate() -> None:
    portal_files = files(
        ("hyprland",),
        (HYPRLAND, GNOME),
        (
            PortalsConf(
                f"{USER_CONFIG}/hyprland-portals.conf", usable=False, error="no [preferred] group"
            ),
            conf(f"{USER_CONFIG}/portals.conf", ("default", ("gnome",))),
        ),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert route.backend == GNOME
    assert any("no [preferred] group" in step for step in route.trace)


def test_missing_backend_falls_through_to_the_next_directory_since_1_21_1() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME, GTK),
        (
            conf(f"{USER_CONFIG}/portals.conf", ("default", ("kde",))),
            conf(f"{SYSTEM}/gnome-portals.conf", ("default", ("gnome", "gtk"))),
        ),
    )
    new = resolve_route(SC, portal_files, NEW)
    assert (new.backend, new.rule, new.config) == (
        GNOME,
        Rule.DEFAULT,
        f"{SYSTEM}/gnome-portals.conf",
    )
    assert any("kde is listed but not installed" in step for step in new.trace)
    # Before 1.21.1 only the user's file is read; it names nothing usable, so UseIn decides.
    old = resolve_route(SC, portal_files, V120)
    assert (old.backend, old.rule) == (GNOME, Rule.USE_IN)


def test_none_disables_the_interface() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME,),
        (conf(f"{SYSTEM}/gnome-portals.conf", ("default", ("gnome",)), (SC, ("none",))),),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert (route.kind, route.rule, route.backend) == (RouteKind.DISABLED, Rule.NONE, None)


def test_default_none_is_overridden_by_an_interface_entry() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME,),
        (conf(f"{SYSTEM}/portals.conf", ("default", ("none",)), (SC, ("gnome",))),),
    )
    assert resolve_route(SC, portal_files, NEW).backend == GNOME
    assert resolve_route(FC, portal_files, NEW).kind is RouteKind.DISABLED


def test_default_star_works_only_since_1_21_1() -> None:
    portal_files = files(
        ("sway",), (GNOME, WLR), (conf(f"{SYSTEM}/portals.conf", ("default", ("*",))),)
    )
    new = resolve_route(SC, portal_files, NEW)
    assert (new.backend, new.rule) == (WLR, Rule.DEFAULT)  # UseIn=sway sorts wlr first
    old = resolve_route(SC, portal_files, V120)
    # 1.19-1.21.0 looked up "*" with the key name "default" as interface: nothing matched.
    assert (old.backend, old.rule) == (WLR, Rule.USE_IN)


def test_star_prefers_backends_whose_use_in_matches() -> None:
    portal_files = files(("sway",), (GNOME, WLR), (conf(f"{SYSTEM}/portals.conf", (SC, ("*",))),))
    # wlr has UseIn=sway, so it sorts before gnome.
    assert resolve_route(SC, portal_files, NEW).backend == WLR
    assert resolve_route(SC, portal_files, V120).backend == WLR  # interface entries were fine


def test_list_order_is_ignored_before_1_19() -> None:
    no_use_in = (desc("gnome", SC), desc("wlr", SC))
    portal_files = files(
        ("x",), no_use_in, (conf(f"{SYSTEM}/portals.conf", ("default", ("wlr", "gnome"))),)
    )
    assert resolve_route(SC, portal_files, V119).backend == no_use_in[1]  # wlr: list order
    assert resolve_route(SC, portal_files, V118).backend == no_use_in[0]  # gnome: name order


def test_interface_entry_replaced_default_before_1_19() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME,),
        (conf(f"{SYSTEM}/portals.conf", ("default", ("gnome",)), (SC, ("kde",))),),
    )
    assert resolve_route(SC, portal_files, V119).rule is Rule.DEFAULT
    assert resolve_route(SC, portal_files, V118).rule is Rule.USE_IN


def test_before_1_17_only_use_in_counts() -> None:
    portal_files = files(
        ("gnome",), (GNOME, WLR), (conf(f"{SYSTEM}/portals.conf", ("default", ("wlr",))),)
    )
    route = resolve_route(SC, portal_files, V116)
    assert (route.backend, route.rule) == (GNOME, Rule.USE_IN)
    assert any("before 1.17" in step for step in route.trace)


def test_descriptors_outside_usr_share_need_1_20_1() -> None:
    user = desc(
        "hyprland",
        SC,
        use_in=("hyprland",),
        directory="/home/u/.local/share/xdg-desktop-portal/portals",
    )
    portal_files = files(("hyprland",), (user,))
    assert resolve_route(SC, portal_files, NEW).backend == user
    old = resolve_route(SC, portal_files, V120.__class__((1, 20, 0)))
    assert old.kind is RouteKind.NOTHING
    assert any("not read by this portal version" in step for step in old.trace)


def test_first_descriptor_of_a_name_wins() -> None:
    user = desc("gnome", FC, directory="/home/u/.local/share/xdg-desktop-portal/portals")
    portal_files = files(("gnome",), (user, GNOME))
    route = resolve_route(SC, portal_files, NEW)
    assert route.kind is RouteKind.NOTHING  # the user's gnome.portal hides the system one
    assert any("was loaded first" in step for step in route.trace)


def test_broken_descriptor_is_skipped() -> None:
    broken = PortalDescriptor(
        "gnome", f"{SYSTEM}/portals/gnome.portal", error="no DBusName in [portal]"
    )
    route = resolve_route(SC, files(("gnome",), (broken, GTK)), NEW)
    assert route.kind is RouteKind.NOTHING
    assert any("no DBusName" in step for step in route.trace)


def test_gtk_is_the_last_resort() -> None:
    route = resolve_route(
        FC,
        files(("mydesktop",), (desc("gtk", FC, bus="org.freedesktop.impl.portal.desktop.gtk"),)),
        NEW,
    )
    assert route.rule is Rule.GTK_FALLBACK


def test_nothing_implements_screencast() -> None:
    route = resolve_route(SC, files(("gnome",), (GTK,)), NEW)
    assert (route.kind, route.rule) == (RouteKind.NOTHING, Rule.NO_MATCH)


def test_unreadable_file_makes_the_prediction_uncertain() -> None:
    portal_files = files(
        ("gnome",),
        (GNOME,),
        (conf(f"{SYSTEM}/gnome-portals.conf", ("default", ("gnome",))),),
        unreadable=(f"{USER_CONFIG}/gnome-portals.conf",),
    )
    route = resolve_route(SC, portal_files, NEW)
    assert route.backend == GNOME
    assert route.uncertain == (f"{USER_CONFIG}/gnome-portals.conf exists but could not be read",)


def test_unknown_version_is_uncertain_and_uses_the_newest_rules() -> None:
    route = resolve_route(SC, files(("gnome",), (GNOME,)), PortalBehaviour(None))
    assert route.backend == GNOME
    assert "version is unknown" in route.uncertain[0]


def test_use_in_is_case_insensitive() -> None:
    assert resolve_route(SC, files(("kde",), (KDE,)), NEW).backend == KDE


@pytest.mark.parametrize(
    ("raw", "version"),
    [
        ("1.21.1+ds-1ubuntu3.1", (1, 21, 1)),
        ("1.20.3-1.fc43", (1, 20, 3)),
        ("1:1.18.4-2", (1, 18, 4)),
        ("1.19", (1, 19, 0)),
        ("", None),
        (None, None),
        ("unknown", None),
    ],
)
def test_parse_portal_version(raw: str | None, version: tuple[int, int, int] | None) -> None:
    assert parse_portal_version(raw) == version


_names = st.sampled_from(["gnome", "gtk", "kde", "wlr", "*", "none", "missing"])
_entries = st.lists(
    st.tuples(st.sampled_from(["default", SC, FC]), st.lists(_names, max_size=3).map(tuple)),
    max_size=3,
)


@given(
    st.lists(st.sampled_from([GNOME, GTK, KDE, WLR, HYPRLAND]), max_size=5),
    st.lists(_entries, max_size=3),
    st.sampled_from([NEW, V120, V119, V118, V116]),
)
def test_prediction_is_always_consistent(
    descriptors: list[PortalDescriptor],
    entry_sets: list[list[tuple[str, tuple[str, ...]]]],
    behaviour: PortalBehaviour,
) -> None:
    configs = tuple(
        conf(f"/etc/xdg/xdg-desktop-portal/{i}-portals.conf", *dict(entries).items())
        for i, entries in enumerate(entry_sets)
    )
    route = resolve_route(SC, files(("gnome",), tuple(descriptors), configs), behaviour)
    if route.kind is RouteKind.BACKEND:
        assert route.backend is not None
        assert SC in route.backend.interfaces
    else:
        assert route.backend is None
    if route.kind is RouteKind.DISABLED:
        assert any("none" in names for entries in entry_sets for _, names in entries)
