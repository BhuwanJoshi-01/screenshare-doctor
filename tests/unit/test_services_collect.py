"""Asking the user manager (WLD-003)."""

from __future__ import annotations

import pytest

from screenshare_doctor.collectors.services import (
    SYSTEMCTL_TIMEOUT,
    UNIT_PROPERTIES,
    UNITS,
    collect_services,
)
from screenshare_doctor.models import FailureKind, ServiceFacts
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_fixture

SHOW = ("systemctl", "--user", "--no-pager", "show")
SHOW += tuple(part for name in UNIT_PROPERTIES for part in ("-p", name)) + UNITS
SHOW_ENV = ("systemctl", "--user", "--no-pager", "show-environment")


def test_real_ubuntu_gnome_manager() -> None:
    runner = FakeRunner()
    runner.script(*SHOW, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script(*SHOW_ENV, stdout=read_fixture("systemctl", "show-environment-ubuntu-gnome.txt"))
    facts, failures = collect_services(runner)
    assert failures == ()
    assert facts.services is not None
    assert facts.services[0].active_state == "active"
    assert facts.activation_environment is not None
    assert facts.activation_environment.current_desktop == "ubuntu:GNOME"
    assert all(call.timeout == SYSTEMCTL_TIMEOUT for call in runner.calls)


def test_no_systemd_is_unknown() -> None:
    runner = FakeRunner()
    runner.script_result(CommandResult(SHOW, Outcome.NOT_FOUND, error="No such file"))
    facts, failures = collect_services(runner)
    assert facts == ServiceFacts()
    assert [f.kind for f in failures] == [FailureKind.NOT_FOUND]
    assert len(runner.calls) == 1


def test_no_user_manager_stops_after_one_command() -> None:
    runner = FakeRunner()
    runner.script(
        *SHOW,
        stderr="Failed to connect to user scope bus via local transport: No medium found",
        returncode=1,
    )
    facts, failures = collect_services(runner)
    assert facts == ServiceFacts()
    assert "No medium found" in failures[0].detail
    assert len(runner.calls) == 1


def test_empty_answer_is_malformed() -> None:
    runner = FakeRunner()
    runner.script(*SHOW, stdout="\n")
    facts, failures = collect_services(runner)
    assert facts.services is None
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT


def test_environment_failure_keeps_the_unit_states() -> None:
    runner = FakeRunner()
    runner.script(*SHOW, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script_result(CommandResult(SHOW_ENV, Outcome.TIMEOUT, duration=5.0))
    facts, failures = collect_services(runner)
    assert facts.services is not None
    assert facts.activation_environment is None
    assert [f.kind for f in failures] == [FailureKind.TIMEOUT]


@pytest.mark.parametrize(
    "verb", ["start", "restart", "stop", "reload", "enable", "import-environment"]
)
def test_never_changes_the_manager(verb: str) -> None:
    runner = FakeRunner()
    runner.script(*SHOW, stdout=read_fixture("systemctl", "show-units-ubuntu-gnome.txt"))
    runner.script(*SHOW_ENV, stdout="")
    collect_services(runner)
    for call in runner.calls:
        assert verb not in call.argv
        assert call.argv[3] in {"show", "show-environment"}
