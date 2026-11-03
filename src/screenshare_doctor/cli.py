"""Command-line interface: parses arguments and wires the layers together.

No diagnosis logic lives here; commands call collectors, rules and renderers.
"""

from __future__ import annotations

import os
import sys
from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

from screenshare_doctor import __version__
from screenshare_doctor.bundles import bundle_for
from screenshare_doctor.bundles.check import check_bundle
from screenshare_doctor.desktops import DesktopFamily, identify_desktop
from screenshare_doctor.exit_codes import ExitCode
from screenshare_doctor.models import SessionEnvironment, SessionFacts, Status
from screenshare_doctor.orchestrator import (
    diagnose,
    inspect_all,
    inspect_dbus,
    inspect_routes,
    inspect_services,
    inspect_session,
)
from screenshare_doctor.privacy import RedactionContext, Redactor, redact_snapshot
from screenshare_doctor.reports.findings import render_findings
from screenshare_doctor.reports.terminal import (
    render_dbus,
    render_desktop,
    render_route,
    render_services,
    render_session,
)
from screenshare_doctor.routes import normalize_interface
from screenshare_doctor.rules.catalog import builtin_rules
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


@app.command()
def doctor(
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Exit with code 1 when any check fails."),
    ] = False,
    show_all: Annotated[
        bool,
        typer.Option("--all", help="Also show findings that follow from another one."),
    ] = False,
) -> None:
    """Run every check, from the session to PipeWire, and explain what needs attention.

    Passive: reads session variables, the package database, the user manager, portal
    files, the session bus (only already-running services are contacted, with
    --auto-start=no) and a running PipeWire. Nothing is started, changed or recorded.
    """
    snapshot = diagnose(inspect_all(SubprocessRunner()))
    render_findings(redact_snapshot(snapshot), Console(highlight=False), show_all=show_all)
    if strict and any(f.status is Status.FAIL for f in snapshot.findings):
        raise typer.Exit(ExitCode.STRICT_FAILURE)


rules_app = typer.Typer(
    help="List the checks, or explain one.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(rules_app, name="rules")


@rules_app.command("list")
def rules_list() -> None:
    """List every check with its code and the layer it judges."""
    console = Console(highlight=False)
    for rule in builtin_rules():
        console.print(
            Text.assemble(
                (f"{rule.id:<20}", "bold"), (f"{rule.layer.value:<16}", "dim"), rule.title
            )
        )


@rules_app.command("explain")
def rules_explain(
    code: Annotated[str, typer.Argument(help="A check code, e.g. SSD-PORTAL-002.")],
) -> None:
    """Explain what one check looks at and how it decides."""
    rule = builtin_rules().get(code)
    if rule is None:
        typer.echo(
            f"screenshare-doctor: no check {code!r}; see screenshare-doctor rules list", err=True
        )
        raise typer.Exit(ExitCode.ERROR)
    console = Console(highlight=False)
    console.print(Text(f"{rule.id}  {rule.title}", style="bold"))
    console.print(Text(f"Layer: {rule.layer.value}", style="dim"))
    console.print()
    console.print(Text(rule.explanation))


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


@check_app.command("services")
def check_services() -> None:
    """Show the installed portal, PipeWire and WirePlumber packages and their user services.

    Reads the package database (dpkg-query, rpm or pacman, query commands only) and the
    user manager (systemctl --user show, show-environment). Nothing is started: a portal
    that is not running stays that way.
    """
    snapshot = inspect_services(SubprocessRunner())
    render_services(redact_snapshot(snapshot), Console(highlight=False))


@check_app.command("dbus")
def check_dbus() -> None:
    """Show which portal services are on the session bus and what they offer for ScreenCast.

    Asks the bus daemon which names run (NameHasOwner) or could start
    (ListActivatableNames), then introspects only the running ones with busctl
    --auto-start=no. A portal that is not running is reported, never started. Exits
    with code 3 when the session bus cannot be reached.
    """
    snapshot = inspect_dbus(SubprocessRunner())
    render_dbus(redact_snapshot(snapshot), Console(highlight=False))
    if snapshot.dbus is None or snapshot.dbus.reachable is not True:
        raise typer.Exit(ExitCode.CONTEXT_UNAVAILABLE)


class BundleChoice(StrEnum):
    GNOME = "gnome"
    KDE = "kde"
    HYPRLAND = "hyprland"
    WLROOTS = "wlroots"


@check_app.command("desktop")
def check_desktop(
    as_desktop: Annotated[
        BundleChoice | None,
        typer.Option(
            "--as",
            help="Compare with this desktop's defaults instead of the detected one.",
        ),
    ] = None,
) -> None:
    """Compare the screen-sharing setup with what this desktop ships by default.

    Checks the desktop's backend package, its .portal file, the desktop's portals.conf,
    the ScreenCast route, whether the backend can run, and the compositor service it
    needs. The defaults come with their sources (docs/desktops.md); a different setup is
    a warning, not a failure, because it can be a deliberate choice.
    """
    snapshot = inspect_routes(SubprocessRunner())
    redacted = redact_snapshot(snapshot)
    if as_desktop is not None:
        family = DesktopFamily(as_desktop.value)
        how = "chosen with --as"
    else:
        activation = snapshot.services.activation_environment if snapshot.services else None
        env = activation or (
            snapshot.session.environment if snapshot.session else SessionEnvironment()
        )
        identity = identify_desktop(env)
        family = identity.family
        whose = "the user manager" if activation is not None else "this shell"
        how = f"from {identity.source} of {whose}" if identity.source else "not detected"
    bundle = bundle_for(family)
    expectations = check_bundle(bundle, snapshot) if bundle is not None else ()
    render_desktop(redacted, bundle, expectations, how, Console(highlight=False))


routes_app = typer.Typer(
    help="Explain which portal backend handles an interface, and why.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(routes_app, name="routes")


@routes_app.command("explain")
def routes_explain(
    interface: Annotated[
        str,
        typer.Argument(
            help="Portal interface: ScreenCast, Screenshot, RemoteDesktop… (short or full name).",
        ),
    ] = "ScreenCast",
) -> None:
    """Predict the backend xdg-desktop-portal uses for INTERFACE, and check it on D-Bus.

    Follows the frontend's own rules for the installed version: its XDG_CURRENT_DESKTOP
    and directories (from the user manager), every portals.conf candidate in search
    order, and the .portal descriptors. Then compares the prediction with the session
    bus, without starting anything.
    """
    impl = normalize_interface(interface)
    if impl is None:
        typer.echo(
            f"screenshare-doctor: {interface!r} is not a portal interface name "
            "(try ScreenCast or org.freedesktop.portal.ScreenCast)",
            err=True,
        )
        raise typer.Exit(ExitCode.ERROR)
    snapshot = inspect_routes(SubprocessRunner())
    render_route(redact_snapshot(snapshot), impl, Console(highlight=False))


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
