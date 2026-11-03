"""Asking PipeWire without starting it."""

from __future__ import annotations

import pytest

from screenshare_doctor.collectors.pipewire import (
    OBJECT_TYPES,
    PW_DUMP_TIMEOUT,
    collect_pipewire,
    may_connect,
)
from screenshare_doctor.models import FailureKind, PipeWireFacts, ServiceFacts, UserService
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_fixture

RUNNING = ServiceFacts(
    services=(UserService("pipewire.service", "loaded", "active", "running", "enabled"),)
)
FIXTURE = {
    "PipeWire:Interface:Core": "pw-dump-core-ubuntu.json",
    "PipeWire:Interface:Client": "pw-dump-clients-ubuntu.json",
    "PipeWire:Interface:Node": "pw-dump-nodes-ubuntu.json",
}


def dump(object_type: str) -> tuple[str, ...]:
    return ("pw-dump", "-N", "-i", "0", object_type)


def _real_runner() -> FakeRunner:
    runner = FakeRunner()
    for object_type in OBJECT_TYPES:
        runner.script(*dump(object_type), stdout=read_fixture("pipewire", FIXTURE[object_type]))
    return runner


def test_real_ubuntu_pipewire() -> None:
    runner = _real_runner()
    facts, failures = collect_pipewire(runner, RUNNING)
    assert failures == ()
    assert facts == PipeWireFacts(
        version="1.6.2",
        clients=("Mutter", "WirePlumber", "gnome-shell", "xdg-desktop-portal"),
        other_clients=12,
        camera_sources=1,
        other_video_sources=0,
        video_streams=0,
    )
    assert all(call.timeout == PW_DUMP_TIMEOUT for call in runner.calls)


@pytest.mark.parametrize("state", ["inactive", "failed", "activating", None])
def test_stopped_pipewire_is_not_contacted(state: str | None) -> None:
    services = ServiceFacts(
        services=(UserService("pipewire.service", "loaded", state, None, "enabled"),)
    )
    runner = FakeRunner()
    facts, failures = collect_pipewire(runner, services)
    assert runner.calls == []
    assert failures == ()
    assert facts.skipped is not None
    assert "connecting would start it" in facts.skipped


def test_unknown_service_state_is_not_risked() -> None:
    runner = FakeRunner()
    facts, _ = collect_pipewire(runner, ServiceFacts())
    assert runner.calls == []
    assert facts.skipped is not None
    assert "unknown" in facts.skipped


def test_without_systemd_there_is_no_socket_activation() -> None:
    assert may_connect(ServiceFacts(), systemd_missing=True) is None
    assert may_connect(None, systemd_missing=True) is None


def test_unit_missing_from_the_answer_is_not_risked() -> None:
    services = ServiceFacts(services=(UserService("wireplumber.service", "loaded", "active"),))
    assert may_connect(services, systemd_missing=False) is not None


def test_missing_pw_dump() -> None:
    runner = FakeRunner()
    runner.script_result(
        CommandResult(dump(OBJECT_TYPES[0]), Outcome.NOT_FOUND, error="No such file")
    )
    facts, failures = collect_pipewire(runner, RUNNING)
    assert facts == PipeWireFacts()
    assert failures[0].kind is FailureKind.NOT_FOUND
    assert len(runner.calls) == 1


def test_daemon_that_does_not_answer() -> None:
    runner = FakeRunner()
    runner.script(
        *dump(OBJECT_TYPES[0]), stderr='Error: "failed to connect: Host is down"', returncode=1
    )
    facts, failures = collect_pipewire(runner, RUNNING)
    assert facts.version is None
    assert "Host is down" in failures[0].detail


def test_truncated_dump_is_not_parsed() -> None:
    runner = _real_runner()
    runner.script_result(
        CommandResult(dump(OBJECT_TYPES[2]), Outcome.OK, 0, stdout="[", stdout_truncated=True)
    )
    facts, failures = collect_pipewire(runner, RUNNING)
    assert facts == PipeWireFacts()
    assert "truncated" in failures[0].detail


def test_malformed_dump() -> None:
    runner = _real_runner()
    runner.script(*dump(OBJECT_TYPES[1]), stdout="{}")
    _, failures = collect_pipewire(runner, RUNNING)
    assert failures[0].kind is FailureKind.MALFORMED_OUTPUT


def test_only_pw_dump_is_run() -> None:
    runner = _real_runner()
    collect_pipewire(runner, RUNNING)
    assert {call.argv[0] for call in runner.calls} == {"pw-dump"}
    assert all("-m" not in call.argv and "--monitor" not in call.argv for call in runner.calls)
