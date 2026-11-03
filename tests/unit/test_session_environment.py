"""Reading the session variables (WLD-001)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from screenshare_doctor.collectors.environment import read_session_environment
from screenshare_doctor.models import SessionEnvironment
from tests.fakes import read_env_fixture


def _read(environ: Mapping[str, str]) -> SessionEnvironment:
    return read_session_environment(environ)


def test_real_gnome_wayland_session_is_read_as_found() -> None:
    env = _read(read_env_fixture("gnome-wayland-ubuntu"))
    assert env == SessionEnvironment(
        session_type="wayland",
        current_desktop="ubuntu:GNOME",
        session_desktop="ubuntu",
        desktop_session="ubuntu",
        wayland_display="wayland-0",
        display=":0",
        runtime_dir="/run/user/1000",
        session_id=None,
        dbus_session_bus_address="unix:path=/run/user/1000/bus",
        ssh=False,
    )


@pytest.mark.parametrize(
    ("fixture", "session_type", "desktop", "wayland_display"),
    [
        ("kde-plasma-wayland", "wayland", "KDE", "wayland-0"),
        ("hyprland", "wayland", "Hyprland", "wayland-1"),
        ("gnome-x11", "x11", "GNOME", None),
        ("ssh-shell", "tty", None, None),
        ("linux-console", "tty", None, None),
    ],
)
def test_synthetic_sessions(
    fixture: str, session_type: str, desktop: str | None, wayland_display: str | None
) -> None:
    env = _read(read_env_fixture(fixture))
    assert env.session_type == session_type
    assert env.current_desktop == desktop
    assert env.wayland_display == wayland_display


def test_empty_environment_reads_as_nothing_set() -> None:
    assert _read({}) == SessionEnvironment()


def test_empty_values_count_as_unset() -> None:
    env = _read({"WAYLAND_DISPLAY": "", "XDG_CURRENT_DESKTOP": "  ", "DISPLAY": ":0"})
    assert env.wayland_display is None
    assert env.current_desktop is None
    assert env.display == ":0"


def test_values_are_not_normalised() -> None:
    env = _read({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "Wayland"})
    assert env.current_desktop == "ubuntu:GNOME"
    assert env.session_type == "Wayland"


@pytest.mark.parametrize("variable", ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"])
def test_any_ssh_variable_marks_an_ssh_login(variable: str) -> None:
    assert _read({variable: "192.0.2.10 51514 22"}).ssh is True


def test_ssh_values_are_not_kept() -> None:
    env = _read(read_env_fixture("ssh-shell"))
    assert env.ssh is True
    assert "192.0.2" not in repr(env)


@pytest.mark.parametrize(
    ("address", "kept"),
    [
        ("unix:path=/run/user/1000/bus,guid=0123456789abcdef", "unix:path=/run/user/1000/bus"),
        ("unix:guid=0123456789abcdef,path=/run/user/1000/bus", "unix:path=/run/user/1000/bus"),
        ("unix:path=/run/user/1000/bus", "unix:path=/run/user/1000/bus"),
        (
            "unix:abstract=/tmp/dbus-XYZ,guid=abc;unix:path=/run/bus",
            "unix:abstract=/tmp/dbus-XYZ;unix:path=/run/bus",
        ),
        ("disabled:", "disabled:"),
    ],
)
def test_bus_address_loses_its_guid(address: str, kept: str) -> None:
    assert _read({"DBUS_SESSION_BUS_ADDRESS": address}).dbus_session_bus_address == kept


class _GuardedEnviron(Mapping[str, str]):
    """An environment that refuses to be listed and records every name looked up."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values
        self.looked_up: set[str] = set()

    def __getitem__(self, key: str) -> str:
        self.looked_up.add(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("the collector listed the whole environment")

    def __len__(self) -> int:
        return len(self._values)


def test_variables_outside_the_allowlist_are_never_read() -> None:
    environ = _GuardedEnviron(read_env_fixture("gnome-wayland-ubuntu") | {"GITHUB_TOKEN": "canary"})
    env = _read(environ)
    assert "GITHUB_TOKEN" not in environ.looked_up
    assert "canary" not in repr(env)
    assert environ.looked_up <= {
        "XDG_SESSION_TYPE",
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "XDG_RUNTIME_DIR",
        "XDG_SESSION_ID",
        "DBUS_SESSION_BUS_ADDRESS",
        "SSH_CONNECTION",
        "SSH_CLIENT",
        "SSH_TTY",
    }
