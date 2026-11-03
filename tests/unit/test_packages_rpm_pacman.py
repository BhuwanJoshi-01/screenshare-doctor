"""rpm and pacman output (WLD-002)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.packages import PACKAGES, parse_pacman, parse_rpm
from screenshare_doctor.models import PackageInfo, PackageState
from tests.fakes import read_fixture

OK = PackageState.INSTALLED
N = PackageState.NOT_INSTALLED
U = PackageState.UNKNOWN


def test_rpm_fedora_capture() -> None:
    packages = parse_rpm(read_fixture("packages", "rpm-fedora-gnome.stdout"))
    assert packages == (
        PackageInfo("xdg-desktop-portal", OK, "1.20.3-1.fc43"),
        PackageInfo("xdg-desktop-portal-gnome", OK, "49.0-1.fc43"),
        PackageInfo("xdg-desktop-portal-gtk", OK, "1.15.3-2.fc43"),
        PackageInfo("xdg-desktop-portal-kde", N),
        PackageInfo("xdg-desktop-portal-wlr", N),
        PackageInfo("xdg-desktop-portal-hyprland", N),
        PackageInfo("pipewire", OK, "1.4.9-1.fc43"),
        PackageInfo("wireplumber", OK, "0.5.12-1.fc43"),
    )


def test_rpm_keeps_the_first_of_two_architectures() -> None:
    packages = parse_rpm("pipewire\t1.4.9-1\npipewire\t1.4.8-1\n", names=("pipewire",))
    assert packages == (PackageInfo("pipewire", OK, "1.4.9-1"),)


def test_rpm_without_any_answer_is_unknown() -> None:
    assert parse_rpm("", names=("pipewire",)) == (PackageInfo("pipewire", U),)


def test_pacman_arch_capture() -> None:
    packages = parse_pacman(
        read_fixture("packages", "pacman-arch-hyprland.stdout"),
        read_fixture("packages", "pacman-arch-hyprland.stderr"),
    )
    assert packages == (
        PackageInfo("xdg-desktop-portal", OK, "1.20.3-1"),
        PackageInfo("xdg-desktop-portal-gnome", N),
        PackageInfo("xdg-desktop-portal-gtk", OK, "1.15.3-1"),
        PackageInfo("xdg-desktop-portal-kde", N),
        PackageInfo("xdg-desktop-portal-wlr", N),
        PackageInfo("xdg-desktop-portal-hyprland", OK, "1.3.10-2"),
        PackageInfo("pipewire", OK, "1:1.4.9-1"),
        PackageInfo("wireplumber", OK, "0.5.12-1"),
    )


def test_pacman_ignores_other_lines() -> None:
    packages = parse_pacman("warning: something\npipewire 1.4\n", "", names=("pipewire",))
    assert packages == (PackageInfo("pipewire", OK, "1.4"),)


@given(st.text(), st.text())
def test_every_requested_name_gets_exactly_one_answer(stdout: str, stderr: str) -> None:
    assert tuple(p.name for p in parse_rpm(stdout)) == PACKAGES
    assert tuple(p.name for p in parse_pacman(stdout, stderr)) == PACKAGES
