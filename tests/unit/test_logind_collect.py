"""Asking logind about the sessions (WLD-001)."""

from __future__ import annotations

import pytest

from screenshare_doctor.collectors.logind import LOGINCTL_TIMEOUT, collect_logind
from screenshare_doctor.models import FailureKind, LogindFacts, SessionEnvironment
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, UnexpectedCommandError, read_fixture

PROPS = ("-p", "Id", "-p", "Type", "-p", "Class", "-p", "Remote")
PROPS += ("-p", "Desktop", "-p", "State", "-p", "Active", "-p", "Seat")
SHOW_USER = ("loginctl", "--no-pager", "show-user", "1000", "-p", "Display")


def show_session(session_id: str) -> tuple[str, ...]:
    return ("loginctl", "--no-pager", "show-session", session_id, *PROPS)


def test_terminal_under_the_user_manager_finds_the_display_session() -> None:
    # The real situation on the development machine: no XDG_SESSION_ID at all.
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout=read_fixture("loginctl", "show-user-display-gnome.txt"))
    runner.script(
        *show_session("63"), stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt")
    )
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert failures == ()
    assert facts.own is None
    assert facts.display is not None
    assert (facts.display.id, facts.display.session_type) == ("63", "wayland")
    assert facts.display_known
    assert all(call.timeout == LOGINCTL_TIMEOUT for call in runner.calls)


def test_terminal_inside_the_desktop_asks_once_per_session() -> None:
    runner = FakeRunner()
    runner.script(
        *show_session("2"), stdout=read_fixture("loginctl", "show-session-kde-wayland.txt")
    )
    runner.script(*SHOW_USER, stdout="Display=2\n")
    facts, failures = collect_logind(runner, SessionEnvironment(session_id="2"), uid=1000)
    assert failures == ()
    assert facts.own is not None
    assert facts.display is facts.own
    assert len(runner.calls) == 2


def test_ssh_login_sees_its_own_session_and_the_desktop() -> None:
    runner = FakeRunner()
    runner.script(*show_session("7"), stdout=read_fixture("loginctl", "show-session-ssh.txt"))
    runner.script(*SHOW_USER, stdout=read_fixture("loginctl", "show-user-display-gnome.txt"))
    runner.script(
        *show_session("63"), stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt")
    )
    facts, failures = collect_logind(runner, SessionEnvironment(session_id="7"), uid=1000)
    assert failures == ()
    assert facts.own is not None
    assert facts.own.remote is True
    assert facts.display is not None
    assert facts.display.session_type == "wayland"


def test_no_graphical_session_is_a_known_answer() -> None:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout=read_fixture("loginctl", "show-user-no-display.txt"))
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert facts == LogindFacts(display_known=True)
    assert failures == ()


def test_missing_loginctl_stops_after_the_first_command() -> None:
    runner = FakeRunner()
    argv = show_session("5")
    runner.script_result(CommandResult(argv, Outcome.NOT_FOUND, error="No such file"))
    facts, failures = collect_logind(runner, SessionEnvironment(session_id="5"), uid=1000)
    assert facts == LogindFacts()
    assert [f.kind for f in failures] == [FailureKind.NOT_FOUND]
    assert len(runner.calls) == 1


def test_missing_loginctl_without_session_id() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW_USER, Outcome.NOT_FOUND, error="No such file"))
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert facts == LogindFacts()
    assert facts.display_known is False
    assert [(f.probe, f.kind) for f in failures] == [("loginctl show-user", FailureKind.NOT_FOUND)]


def test_stale_session_id_still_finds_the_desktop() -> None:
    runner = FakeRunner()
    runner.script(
        *show_session("999"),
        stderr="Failed to get path for session '999': No session '999' known",
        returncode=1,
    )
    runner.script(*SHOW_USER, stdout="Display=63\n")
    runner.script(
        *show_session("63"), stdout=read_fixture("loginctl", "show-session-gnome-wayland.txt")
    )
    facts, failures = collect_logind(runner, SessionEnvironment(session_id="999"), uid=1000)
    assert facts.own is None
    assert facts.display is not None
    assert len(failures) == 1
    assert failures[0].kind is FailureKind.NONZERO_EXIT
    assert "No session '999' known" in failures[0].detail


def test_unknown_user_is_a_failure_not_an_empty_answer() -> None:
    # Real systemd 259 message for a uid it does not know.
    runner = FakeRunner()
    runner.script(*SHOW_USER, stderr="Failed to look up user 1000: No such process", returncode=1)
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert facts.display_known is False
    assert failures[0].kind is FailureKind.NONZERO_EXIT


def test_timeout_is_reported() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW_USER, Outcome.TIMEOUT, duration=5.0))
    _, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert failures[0].kind is FailureKind.TIMEOUT


@pytest.mark.parametrize("bad_id", ["../1", "1 2", "-p", "x" * 65, "63\n"])
def test_odd_session_ids_are_never_passed_to_loginctl(bad_id: str) -> None:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout="Display=\n")
    facts, failures = collect_logind(runner, SessionEnvironment(session_id=bad_id), uid=1000)
    assert [call.argv for call in runner.calls] == [SHOW_USER]
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT
    assert facts.own is None


def test_odd_display_property_is_not_followed() -> None:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout="Display=--all\n")
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert facts.display is None
    assert facts.display_known is False
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT


def test_show_session_without_id_is_malformed() -> None:
    runner = FakeRunner()
    runner.script(*SHOW_USER, stdout="Display=63\n")
    runner.script(*show_session("63"), stdout="garbage\n")
    facts, failures = collect_logind(runner, SessionEnvironment(), uid=1000)
    assert facts.display is None
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT


def test_only_show_commands_are_run() -> None:
    runner = FakeRunner()
    with pytest.raises(UnexpectedCommandError):
        collect_logind(runner, SessionEnvironment(), uid=1000)
    for call in runner.calls:
        assert call.argv[:2] == ("loginctl", "--no-pager")
        assert call.argv[2] in {"show-user", "show-session"}
