import pytest

from screenshare_doctor.runner import CommandResult, CommandRunner, Outcome
from tests.fakes import FakeRunner, UnexpectedCommandError


def test_fake_runner_answers_scripted_commands_and_records_calls() -> None:
    fake = FakeRunner()
    fake.script("busctl", "--user", "list", stdout="NAME PID PROCESS\n")
    runner: CommandRunner = fake
    result = runner.run(["busctl", "--user", "list"], timeout=8, env_overrides={"LC_ALL": "C"})
    assert result.ok
    assert result.stdout.startswith("NAME")
    assert fake.calls[0].argv == ("busctl", "--user", "list")
    assert fake.calls[0].env_overrides == {"LC_ALL": "C"}


def test_fake_runner_fails_the_test_on_unscripted_commands() -> None:
    with pytest.raises(UnexpectedCommandError, match="rm"):
        FakeRunner().run(["rm", "-rf", "build"], timeout=1)


def test_fake_runner_can_return_any_outcome() -> None:
    fake = FakeRunner()
    fake.script_result(CommandResult(("busctl",), Outcome.TIMEOUT, duration=5))
    assert fake.run(["busctl"], timeout=5).outcome is Outcome.TIMEOUT
