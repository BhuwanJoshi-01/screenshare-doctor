import dataclasses

import pytest

from screenshare_doctor.models import PathState, SessionEnvironment, SessionPaths


def test_session_environment_defaults_to_nothing_set() -> None:
    env = SessionEnvironment()
    assert env.session_type is None
    assert env.current_desktop is None
    assert env.wayland_display is None
    assert env.ssh is False


def test_session_environment_is_immutable() -> None:
    env = SessionEnvironment(session_type="wayland")
    with pytest.raises(dataclasses.FrozenInstanceError):
        env.session_type = "x11"  # type: ignore[misc]


def test_path_states_are_the_documented_json_strings() -> None:
    assert [state.value for state in PathState] == [
        "socket",
        "directory",
        "other",
        "missing",
        "unreadable",
        "not_checked",
    ]


def test_session_paths_start_unchecked() -> None:
    paths = SessionPaths()
    assert paths.runtime_dir is PathState.NOT_CHECKED
    assert paths.wayland_socket is PathState.NOT_CHECKED
    assert paths.x11_socket is PathState.NOT_CHECKED
    assert paths.wayland_socket_path is None
