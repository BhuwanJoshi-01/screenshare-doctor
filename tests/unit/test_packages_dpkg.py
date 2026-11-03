"""dpkg-query output (WLD-002)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.packages import PACKAGES, parse_dpkg
from screenshare_doctor.models import PackageInfo, PackageState
from tests.fakes import read_fixture

OK = PackageState.INSTALLED
N = PackageState.NOT_INSTALLED
B = PackageState.BROKEN
U = PackageState.UNKNOWN


def test_real_ubuntu_gnome_capture() -> None:
    packages = parse_dpkg(
        read_fixture("packages", "dpkg-ubuntu-gnome.stdout"),
        read_fixture("packages", "dpkg-ubuntu-gnome.stderr"),
    )
    assert packages == (
        PackageInfo("xdg-desktop-portal", OK, "1.21.1+ds-1ubuntu3.1"),
        PackageInfo("xdg-desktop-portal-gnome", OK, "50.0-0ubuntu1"),
        PackageInfo("xdg-desktop-portal-gtk", OK, "1.15.3-2ubuntu1"),
        PackageInfo("xdg-desktop-portal-kde", N),
        PackageInfo("xdg-desktop-portal-wlr", N),
        PackageInfo("xdg-desktop-portal-hyprland", N),
        PackageInfo("pipewire", OK, "1.6.2-1ubuntu1.2"),
        PackageInfo("wireplumber", OK, "0.5.13-1ubuntu1.1"),
    )


def test_odd_dpkg_states() -> None:
    states = {
        p.name: p.state for p in parse_dpkg(read_fixture("packages", "dpkg-odd-states.stdout"), "")
    }
    assert states == {
        "xdg-desktop-portal": OK,
        "xdg-desktop-portal-gnome": N,  # rc: removed, config files left
        "xdg-desktop-portal-gtk": B,  # iF: half configured
        "xdg-desktop-portal-kde": B,  # iiR: reinstallation required
        "xdg-desktop-portal-wlr": U,  # neither listed nor reported missing
        "xdg-desktop-portal-hyprland": U,
        "pipewire": OK,
        "wireplumber": B,  # iU: unpacked only
    }


def test_removed_package_has_no_version() -> None:
    packages = parse_dpkg("xdg-desktop-portal-gnome\t48.0-1\trc \n", "")
    assert packages[1] == PackageInfo("xdg-desktop-portal-gnome", N)


def test_triggers_pending_counts_as_installed() -> None:
    packages = parse_dpkg("pipewire\t1.6.2\tit \nwireplumber\t0.5\tiW \n", "")
    assert [p.state for p in packages[-2:]] == [OK, OK]


def test_names_outside_the_list_are_ignored() -> None:
    packages = parse_dpkg("gnome-shell\t50.1\tii \n", "", names=("pipewire",))
    assert packages == (PackageInfo("pipewire", U),)


def test_unknown_status_letter_is_unknown() -> None:
    assert parse_dpkg("pipewire\t1\tiZ \n", "", names=("pipewire",))[0].state is U


@given(st.text(), st.text())
def test_every_requested_name_gets_exactly_one_answer(stdout: str, stderr: str) -> None:
    packages = parse_dpkg(stdout, stderr)
    assert tuple(p.name for p in packages) == PACKAGES
