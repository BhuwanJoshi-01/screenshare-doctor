"""The portal's search order (WLD-005)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.models import XdgDirectories
from screenshare_doctor.portal_paths import (
    config_candidates,
    config_directories,
    descriptor_directories,
    join,
)

# The user manager's values on the Ubuntu 26.04 machine (home shortened to /home/u).
UBUNTU = XdgDirectories(
    home="/home/u",
    config_dirs="/etc/xdg/xdg-ubuntu:/etc/xdg",
    data_dirs=(
        "/usr/share/ubuntu:/usr/share/gnome:/home/u/.local/share/flatpak/exports/share:"
        "/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/:/var/lib/snapd/desktop"
    ),
)


@pytest.mark.xfail(strict=True, reason="WLD-005")
def test_real_ubuntu_config_search_order() -> None:
    assert config_directories(UBUNTU) == (
        "/home/u/.config/xdg-desktop-portal",
        "/etc/xdg/xdg-ubuntu/xdg-desktop-portal",
        "/etc/xdg/xdg-desktop-portal",
        "/etc/xdg-desktop-portal",
        "/home/u/.local/share/xdg-desktop-portal",
        "/usr/share/ubuntu/xdg-desktop-portal",
        "/usr/share/gnome/xdg-desktop-portal",
        "/home/u/.local/share/flatpak/exports/share/xdg-desktop-portal",
        "/var/lib/flatpak/exports/share/xdg-desktop-portal",
        "/usr/local/share/xdg-desktop-portal",
        "/usr/share/xdg-desktop-portal",
        "/var/lib/snapd/desktop/xdg-desktop-portal",
    )


def test_real_ubuntu_descriptor_search_order() -> None:
    dirs = descriptor_directories(UBUNTU)
    assert dirs[0] == "/home/u/.local/share/xdg-desktop-portal/portals"
    assert dirs[1] == "/usr/share/ubuntu/xdg-desktop-portal/portals"
    assert dirs[-1] == "/usr/share/xdg-desktop-portal/portals"


@pytest.mark.xfail(strict=True, reason="WLD-005")
def test_glib_defaults_for_unset_variables() -> None:
    assert config_directories(XdgDirectories(home="/home/u")) == (
        "/home/u/.config/xdg-desktop-portal",
        "/etc/xdg/xdg-desktop-portal",
        "/etc/xdg-desktop-portal",
        "/home/u/.local/share/xdg-desktop-portal",
        "/usr/local/share/xdg-desktop-portal",
        "/usr/share/xdg-desktop-portal",
    )


# Fedora 45 KDE Plasma's user manager: /usr/share comes from XDG_DATA_DIRS and again
# as the portal's built-in DATADIR (home shortened to /home/u).
FEDORA_KDE = XdgDirectories(
    home="/home/u",
    config_dirs="/home/u/.config/kdedefaults:/etc/xdg:/usr/share/kde-settings/kde-profile/default/xdg",
    data_dirs="/usr/share/kde-settings/kde-profile/default/share:/usr/local/share:/usr/share",
)


@pytest.mark.xfail(strict=True, reason="WLD-005")
def test_a_directory_searched_twice_is_listed_once() -> None:
    # The portal stops at the first file found, so the second search of a directory can
    # never change the outcome; listing it twice only confused the explanation.
    for found in (config_directories(FEDORA_KDE), descriptor_directories(FEDORA_KDE)):
        assert len(found) == len(set(found))
    assert config_directories(FEDORA_KDE)[-1] == "/usr/share/xdg-desktop-portal"
    assert descriptor_directories(FEDORA_KDE)[-1] == "/usr/share/xdg-desktop-portal/portals"


def test_explicit_user_directories() -> None:
    dirs = config_directories(XdgDirectories(config_home="/cfg", data_home="/data"))
    assert dirs[0] == "/cfg/xdg-desktop-portal"
    assert "/data/xdg-desktop-portal" in dirs


def test_without_home_the_user_directories_are_unknown() -> None:
    assert config_directories(XdgDirectories())[0] == "/etc/xdg/xdg-desktop-portal"


def test_portal_dir_override_replaces_everything() -> None:
    dirs = XdgDirectories(home="/home/u", portal_dir="/tmp/portals")  # noqa: S108
    assert config_directories(dirs) == ("/tmp/portals",)  # noqa: S108
    assert descriptor_directories(dirs) == ("/tmp/portals",)  # noqa: S108


def test_empty_entries_are_skipped() -> None:
    dirs = config_directories(XdgDirectories(config_dirs="::/etc/xdg:", data_dirs=":/usr/share:"))
    assert dirs.count("/etc/xdg/xdg-desktop-portal") == 1


def test_candidates_in_one_directory() -> None:
    assert config_candidates("/usr/share/xdg-desktop-portal", ("ubuntu", "gnome")) == (
        "/usr/share/xdg-desktop-portal/ubuntu-portals.conf",
        "/usr/share/xdg-desktop-portal/gnome-portals.conf",
        "/usr/share/xdg-desktop-portal/portals.conf",
    )
    assert config_candidates("/d", ()) == ("/d/portals.conf",)


@given(st.lists(st.from_regex(r"/*[ab]{0,3}/*", fullmatch=True), min_size=1, max_size=4))
def test_join_never_doubles_slashes_between_parts(parts: list[str]) -> None:
    assert "//" not in join(*parts)
