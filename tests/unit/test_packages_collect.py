"""Choosing the package manager and falling back to files (WLD-002)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from screenshare_doctor.collectors.packages import (
    DPKG_FORMAT,
    PACKAGE_TIMEOUT,
    PACKAGES,
    RPM_FORMAT,
    collect_packages,
)
from screenshare_doctor.models import FailureKind, PackageInfo, PackageState
from screenshare_doctor.runner import CommandResult, Outcome
from tests.fakes import FakeRunner, read_fixture

DPKG = ("dpkg-query", "-W", "-f", DPKG_FORMAT, *PACKAGES)
RPM = ("rpm", "-q", "--queryformat", RPM_FORMAT, *PACKAGES)
PACMAN = ("pacman", "-Q", *PACKAGES)


def _which(*programs: str) -> Callable[[str], str | None]:
    return lambda name: f"/usr/bin/{name}" if name in programs else None


def _exists(*paths: str) -> Callable[[str], bool]:
    return lambda path: path in paths


def test_dpkg_on_the_real_ubuntu_capture() -> None:
    runner = FakeRunner()
    runner.script(
        *DPKG,
        stdout=read_fixture("packages", "dpkg-ubuntu-gnome.stdout"),
        stderr=read_fixture("packages", "dpkg-ubuntu-gnome.stderr"),
        returncode=1,
    )
    facts, failures = collect_packages(
        runner,
        which=_which("dpkg-query", "pipewire"),
        exists=_exists("/var/lib/dpkg/status"),
    )
    assert failures == ()
    assert facts.source == "dpkg"
    assert facts.packages[0] == PackageInfo(
        "xdg-desktop-portal", PackageState.INSTALLED, "1.21.1+ds-1ubuntu3.1"
    )
    assert runner.calls[0].timeout == PACKAGE_TIMEOUT


def test_rpm_with_the_new_database_location() -> None:
    runner = FakeRunner()
    runner.script(*RPM, stdout=read_fixture("packages", "rpm-fedora-gnome.stdout"), returncode=3)
    facts, failures = collect_packages(
        runner, which=_which("rpm"), exists=_exists("/usr/lib/sysimage/rpm")
    )
    assert (facts.source, failures) == ("rpm", ())


def test_pacman() -> None:
    runner = FakeRunner()
    runner.script(
        *PACMAN,
        stdout=read_fixture("packages", "pacman-arch-hyprland.stdout"),
        stderr=read_fixture("packages", "pacman-arch-hyprland.stderr"),
        returncode=1,
    )
    facts, _ = collect_packages(
        runner, which=_which("pacman"), exists=_exists("/var/lib/pacman/local")
    )
    assert facts.source == "pacman"


def test_a_manager_without_its_database_is_skipped() -> None:
    # rpm installed on Debian (for alien) knows nothing about the system's packages.
    runner = FakeRunner()
    runner.script(*DPKG, stdout=read_fixture("packages", "dpkg-ubuntu-gnome.stdout"))
    facts, _ = collect_packages(
        runner,
        which=_which("dpkg-query", "rpm"),
        exists=_exists("/var/lib/dpkg/status"),
    )
    assert facts.source == "dpkg"
    assert [call.argv[0] for call in runner.calls] == ["dpkg-query"]


def test_no_package_manager_falls_back_to_the_programs() -> None:
    facts, failures = collect_packages(
        FakeRunner(),
        which=_which("pipewire"),
        exists=_exists("/usr/libexec/xdg-desktop-portal", "/usr/lib/xdg-desktop-portal-hyprland"),
    )
    assert failures == ()
    assert facts.source == "files"
    states = {p.name: p.state for p in facts.packages}
    assert states["xdg-desktop-portal"] is PackageState.INSTALLED
    assert states["xdg-desktop-portal-hyprland"] is PackageState.INSTALLED
    assert states["pipewire"] is PackageState.INSTALLED
    # A program that is not found proves nothing.
    assert states["xdg-desktop-portal-gnome"] is PackageState.UNKNOWN
    assert states["wireplumber"] is PackageState.UNKNOWN
    assert PackageState.NOT_INSTALLED not in states.values()


@pytest.mark.parametrize(
    ("result", "kind"),
    [
        (CommandResult(DPKG, Outcome.TIMEOUT, duration=15.0), FailureKind.TIMEOUT),
        (CommandResult(DPKG, Outcome.PERMISSION), FailureKind.PERMISSION_DENIED),
        (
            CommandResult(DPKG, Outcome.NONZERO, 2, stderr="dpkg-query: error: database locked"),
            FailureKind.NONZERO_EXIT,
        ),
        (CommandResult(DPKG, Outcome.OK, 0, stdout="garbage\n"), FailureKind.MALFORMED_OUTPUT),
    ],
)
def test_failed_query_is_recorded_and_files_are_used(
    result: CommandResult, kind: FailureKind
) -> None:
    runner = FakeRunner()
    runner.script_result(result)
    facts, failures = collect_packages(
        runner,
        which=_which("dpkg-query"),
        exists=_exists("/var/lib/dpkg/status", "/usr/libexec/xdg-desktop-portal"),
    )
    assert [f.kind for f in failures] == [kind]
    assert facts.source == "files"
    assert facts.packages[0].state is PackageState.INSTALLED


def test_only_query_commands_are_run() -> None:
    runner = FakeRunner()
    runner.script(*DPKG, stdout="pipewire\t1\tii \n")
    collect_packages(runner, which=_which("dpkg-query"), exists=_exists("/var/lib/dpkg/status"))
    assert [call.argv[:2] for call in runner.calls] == [("dpkg-query", "-W")]
