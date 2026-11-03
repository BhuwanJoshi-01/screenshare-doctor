import pytest

from screenshare_doctor.models import FailureKind, ProbeFailure
from screenshare_doctor.runner import CommandResult, Outcome, probe_failure


def test_only_ok_outcome_counts_as_ok() -> None:
    assert CommandResult(("true",), Outcome.OK, returncode=0).ok
    for outcome in Outcome:
        if outcome is not Outcome.OK:
            assert not CommandResult(("x",), outcome).ok


def test_successful_result_is_not_a_failure() -> None:
    assert probe_failure("busctl", CommandResult(("busctl",), Outcome.OK, 0)) is None


@pytest.mark.parametrize(
    ("result", "kind", "detail"),
    [
        (
            CommandResult(("busctl",), Outcome.NOT_FOUND, error="No such file"),
            FailureKind.NOT_FOUND,
            "busctl was not found",
        ),
        (
            CommandResult(("pw-cli",), Outcome.PERMISSION),
            FailureKind.PERMISSION_DENIED,
            "permission denied when starting pw-cli",
        ),
        (
            CommandResult(("busctl",), Outcome.TIMEOUT, duration=5.04),
            FailureKind.TIMEOUT,
            "busctl did not finish within 5.0 s and was stopped",
        ),
        (
            CommandResult(
                ("busctl",),
                Outcome.NONZERO,
                returncode=1,
                stderr="\nFailed to connect to bus: No medium found\nsecond line\n",
            ),
            FailureKind.NONZERO_EXIT,
            "busctl exited with code 1: Failed to connect to bus: No medium found",
        ),
        (
            CommandResult(("python",), Outcome.OS_ERROR, error="Exec format error"),
            FailureKind.OS_ERROR,
            "python could not be started: Exec format error",
        ),
    ],
)
def test_failed_results_become_probe_failures(
    result: CommandResult, kind: FailureKind, detail: str
) -> None:
    failure = probe_failure("dbus", result)
    assert failure == ProbeFailure("dbus", kind, detail)


def test_failure_detail_is_kept_short() -> None:
    result = CommandResult(("x",), Outcome.NONZERO, returncode=1, stderr="e" * 5000)
    failure = probe_failure("x", result)
    assert failure is not None
    assert len(failure.detail) == 200
    assert failure.detail.endswith("…")


def test_failure_detail_uses_stdout_when_stderr_is_empty() -> None:
    result = CommandResult(
        ("wpctl", "status"),
        Outcome.NONZERO,
        returncode=1,
        stdout="Could not connect to PipeWire\n",
    )
    failure = probe_failure("wireplumber", result)
    assert failure is not None
    assert failure.detail == "wpctl exited with code 1: Could not connect to PipeWire"


def test_failure_detail_prefers_stderr() -> None:
    result = CommandResult(("x",), Outcome.NONZERO, returncode=1, stdout="out", stderr="err")
    failure = probe_failure("x", result)
    assert failure is not None
    assert failure.detail == "x exited with code 1: err"
