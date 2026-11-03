"""Runs the collectors and assembles the snapshot; no diagnosis happens here."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping

from screenshare_doctor import __version__
from screenshare_doctor.collectors.dbus import collect_dbus
from screenshare_doctor.collectors.environment import (
    check_session_paths,
    read_session_environment,
    read_xdg_directories,
)
from screenshare_doctor.collectors.logind import collect_logind
from screenshare_doctor.collectors.packages import collect_packages
from screenshare_doctor.collectors.portal_config import (
    collect_portal_files,
    list_portal_files,
    read_capped,
)
from screenshare_doctor.collectors.services import collect_services
from screenshare_doctor.desktops import parse_desktop_list
from screenshare_doctor.models import ProbeFailure, SessionFacts, Snapshot, utc_timestamp
from screenshare_doctor.runner import CommandRunner


def _exists(path: str) -> bool:
    return os.path.exists(path)  # noqa: PTH110 - same signature as the injected test fakes


def collect_session(
    runner: CommandRunner,
    *,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    stat: Callable[[str], os.stat_result] = os.stat,
) -> tuple[SessionFacts, tuple[ProbeFailure, ...]]:
    """Read the session variables, stat their paths and ask logind, in that order."""
    env = read_session_environment(environ)
    logind, failures = collect_logind(runner, env, uid=os.getuid() if uid is None else uid)
    facts = SessionFacts(environment=env, paths=check_session_paths(env, stat=stat), logind=logind)
    return facts, failures


def inspect_session(
    runner: CommandRunner,
    *,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    stat: Callable[[str], os.stat_result] = os.stat,
) -> Snapshot:
    """A snapshot holding the session facts and why any of them are missing."""
    session, failures = collect_session(runner, environ=environ, uid=uid, stat=stat)
    return Snapshot(
        tool_version=__version__,
        created_at=utc_timestamp(),
        session=session,
        probe_failures=failures,
    )


def inspect_services(
    runner: CommandRunner,
    *,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    stat: Callable[[str], os.stat_result] = os.stat,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = _exists,
) -> Snapshot:
    """The session, the installed packages and the user services, in one snapshot.

    The session is included so that the user manager's environment can be compared
    with the shell's.
    """
    session, session_failures = collect_session(runner, environ=environ, uid=uid, stat=stat)
    packages, package_failures = collect_packages(runner, which=which, exists=exists)
    services, service_failures = collect_services(runner)
    return Snapshot(
        tool_version=__version__,
        created_at=utc_timestamp(),
        session=session,
        packages=packages,
        services=services,
        probe_failures=(*session_failures, *package_failures, *service_failures),
    )


def inspect_dbus(runner: CommandRunner) -> Snapshot:
    """The portal names on the session bus and what the running ones expose."""
    dbus, failures = collect_dbus(runner)
    return Snapshot(
        tool_version=__version__,
        created_at=utc_timestamp(),
        dbus=dbus,
        probe_failures=failures,
    )


def inspect_routes(
    runner: CommandRunner,
    *,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    stat: Callable[[str], os.stat_result] = os.stat,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = _exists,
    read: Callable[[str], bytes | None] = read_capped,
    list_dir: Callable[[str], tuple[str, ...]] = list_portal_files,
) -> Snapshot:
    """Everything a route explanation needs: the frontend's version (packages), its
    environment (user manager), its files, and the bus to check the prediction against.

    The portal's own variables come from the user manager; when it cannot be asked, the
    shell's are used and the snapshot says so.
    """
    session, session_failures = collect_session(runner, environ=environ, uid=uid, stat=stat)
    packages, package_failures = collect_packages(runner, which=which, exists=exists)
    services, service_failures = collect_services(runner)
    if services.activation_environment is not None and services.activation_directories is not None:
        current_desktop = services.activation_environment.current_desktop
        directories = services.activation_directories
        variables_from = "user manager"
    else:
        current_desktop = session.environment.current_desktop
        directories = read_xdg_directories(environ)
        variables_from = "this shell"
    portal_files, file_failures = collect_portal_files(
        parse_desktop_list(current_desktop).names,
        directories,
        read=read,
        list_dir=list_dir,
        variables_from=variables_from,
    )
    dbus, dbus_failures = collect_dbus(runner)
    return Snapshot(
        tool_version=__version__,
        created_at=utc_timestamp(),
        session=session,
        packages=packages,
        services=services,
        dbus=dbus,
        portal_files=portal_files,
        probe_failures=(
            *session_failures,
            *package_failures,
            *service_failures,
            *file_failures,
            *dbus_failures,
        ),
    )
