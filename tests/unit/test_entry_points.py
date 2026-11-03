"""The installed command and ``python -m`` start the same CLI."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

import pytest

from screenshare_doctor import __version__
from screenshare_doctor.runner import Outcome, SubprocessRunner


def _console_script() -> Path:
    name = "screenshare-doctor.exe" if sys.platform == "win32" else "screenshare-doctor"
    return Path(sysconfig.get_path("scripts")) / name


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "-m", "screenshare_doctor", "--version"],
        [str(_console_script()), "--version"],
    ],
    ids=["python -m", "console script"],
)
def test_entry_point_prints_the_version(argv: list[str]) -> None:
    result = SubprocessRunner().run(argv, timeout=30)
    assert result.outcome is Outcome.OK, result.stderr
    assert result.stdout.strip() == f"screenshare-doctor {__version__}"
