"""Runs the collectors and assembles the snapshot; no diagnosis happens here."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from screenshare_doctor import __version__
from screenshare_doctor.collectors.environment import check_session_paths, read_session_environment
from screenshare_doctor.collectors.logind import collect_logind
from screenshare_doctor.models import ProbeFailure, SessionFacts, Snapshot, utc_timestamp
from screenshare_doctor.runner import CommandRunner


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
