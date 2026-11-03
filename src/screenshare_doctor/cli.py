"""Command-line interface: parses arguments and wires the layers together.

No diagnosis logic lives here; commands call collectors, rules and renderers.
"""

from __future__ import annotations

import os
import sys
from typing import Annotated

import typer
from rich.console import Console

from screenshare_doctor import __version__
from screenshare_doctor.exit_codes import ExitCode
from screenshare_doctor.models import SessionFacts
from screenshare_doctor.orchestrator import inspect_session
from screenshare_doctor.privacy import RedactionContext, Redactor, redact_snapshot
from screenshare_doctor.reports.terminal import render_session
from screenshare_doctor.runner import SubprocessRunner
from screenshare_doctor.session import SessionKind, assess_session

HELP = (
    "Find out why screen sharing fails on your Linux Wayland desktop.\n\n"
    "Passive by default: no screen-sharing request or picker is opened, nothing is "
    "recorded, no service is started or restarted, no setting is changed, and no root or "
    "network access is needed."
)

app = typer.Typer(
    name="screenshare-doctor",
    help=HELP,
    no_args_is_help=True,
    add_completion=False,
    # Rich tracebacks print local variables, which can hold environment values.
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"screenshare-doctor {__version__}")
        raise typer.Exit()


@app.callback()
def cli(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Global options (the help text comes from HELP)."""


check_app = typer.Typer(
    help="Check one part of the screen-sharing stack.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(check_app, name="check")


@check_app.command("session")
def check_session() -> None:
    """Show the session type, the desktop and its display sockets, and where this runs.

    Reads a fixed list of session variables, looks at the sockets they point to and asks
    logind (loginctl show-user, show-session). Exits with code 3 when no graphical
    session can be found.
    """
    snapshot = inspect_session(SubprocessRunner())
    render_session(redact_snapshot(snapshot), Console(highlight=False))
    facts = snapshot.session or SessionFacts()
    kind = assess_session(facts.environment, facts.paths, facts.logind).kind
    if kind in {SessionKind.NONE, SessionKind.UNKNOWN}:
        raise typer.Exit(ExitCode.CONTEXT_UNAVAILABLE)


def main() -> None:
    """Console entry point.

    Typer reports usage errors itself (exit code 2) and turns Ctrl+C into 130. Anything
    else that escapes is a bug: print one redacted line instead of a traceback, which
    could contain local values, and exit with 2. ``SSD_DEBUG=1`` shows the traceback.
    """
    try:
        app()
    except Exception as exc:  # SystemExit (normal exits) is not an Exception
        if os.environ.get("SSD_DEBUG"):
            raise
        message = Redactor(RedactionContext.current()).text(str(exc)) or type(exc).__name__
        typer.echo(
            f"screenshare-doctor: internal error: {message}\n"
            "Run it again with SSD_DEBUG=1 to see the traceback, and please report it.",
            err=True,
        )
        sys.exit(ExitCode.ERROR)
