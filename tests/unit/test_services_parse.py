"""systemctl --user show output (WLD-003)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.services import (
    UNITS,
    parse_activation_environment,
    parse_units,
)
from screenshare_doctor.models import SessionEnvironment, UserService, XdgDirectories
from tests.fakes import read_fixture


def test_real_ubuntu_gnome_units() -> None:
    services = {
        s.unit: s for s in parse_units(read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    }
    assert services["xdg-desktop-portal.service"] == UserService(
        "xdg-desktop-portal.service", "loaded", "active", "running", "static"
    )
    assert services["xdg-desktop-portal-gnome.service"].active_state == "active"
    assert services["plasma-xdg-desktop-portal-kde.service"] == UserService(
        "plasma-xdg-desktop-portal-kde.service", "not-found", "inactive", "dead", None
    )
    assert services["pipewire.socket"].unit_file_state == "enabled"
    assert services["wireplumber.service"].sub_state == "running"


def test_units_come_back_in_the_requested_order() -> None:
    services = parse_units(read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    assert tuple(s.unit for s in services) == UNITS


def test_failed_and_masked_units() -> None:
    text = (
        "Id=xdg-desktop-portal.service\nLoadState=loaded\nActiveState=failed\nSubState=failed\n"
        "UnitFileState=static\n\n"
        "Id=pipewire.service\nLoadState=masked\nActiveState=inactive\nSubState=dead\n"
        "UnitFileState=masked\n"
    )
    services = {
        s.unit: s
        for s in parse_units(text, units=("xdg-desktop-portal.service", "pipewire.service"))
    }
    assert services["xdg-desktop-portal.service"].active_state == "failed"
    assert services["pipewire.service"].load_state == "masked"


def test_unit_without_a_block_has_no_states() -> None:
    assert parse_units("", units=("pipewire.service",)) == (UserService("pipewire.service"),)


def test_real_activation_environment_keeps_only_the_allowlist() -> None:
    env, _ = parse_activation_environment(
        read_fixture("systemctl", "show-environment-ubuntu-gnome.txt")
    )
    assert env == SessionEnvironment(
        session_type="wayland",
        current_desktop="ubuntu:GNOME",
        session_desktop="ubuntu",
        desktop_session="ubuntu",
        wayland_display="wayland-0",
        display=":0",
        runtime_dir="/run/user/1000",
        dbus_session_bus_address="unix:path=/run/user/1000/bus",
    )
    assert "placeholder" not in repr(env)


def test_activation_environment_never_keeps_secrets() -> None:
    env, dirs = parse_activation_environment(
        "GITHUB_TOKEN=ghp_canary\nXDG_CURRENT_DESKTOP=Hyprland\n"
    )
    assert env.current_desktop == "Hyprland"
    assert "canary" not in repr(env)
    assert "canary" not in repr(dirs)


def test_hyprland_started_without_importing_its_environment() -> None:
    # The classic Hyprland mistake: the user manager never learned the desktop's variables.
    env, _ = parse_activation_environment("HOME=/home/x\nPATH=/usr/bin\n")
    assert env.current_desktop is None
    assert env.wayland_display is None


@given(st.text())
def test_parsers_never_raise(text: str) -> None:
    assert len(parse_units(text)) == len(UNITS)
    parse_activation_environment(text)


def test_real_activation_directories() -> None:
    _, dirs = parse_activation_environment(
        read_fixture("systemctl", "show-environment-ubuntu-gnome.txt")
    )
    assert dirs == XdgDirectories(
        home="/home/user",
        config_dirs="/etc/xdg/xdg-ubuntu:/etc/xdg",
        data_dirs=(
            "/usr/share/ubuntu:/usr/share/gnome:/home/user/.local/share/flatpak/exports/share:"
            "/var/lib/flatpak/exports/share:/usr/local/share/:/usr/share/:/var/lib/snapd/desktop"
        ),
    )
