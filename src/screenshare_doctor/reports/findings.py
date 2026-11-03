"""Terminal output of a diagnosis: one line per finding, details for what needs attention.

Collected text is added as plain ``Text``, never as Rich markup.
"""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.text import Text

from screenshare_doctor.bundles import bundle_for
from screenshare_doctor.desktops import identify_desktop
from screenshare_doctor.models import Finding, Snapshot, Status
from screenshare_doctor.reports.terminal import portal_version, redaction_line
from screenshare_doctor.rules.engine import root_causes
from screenshare_doctor.session import SessionKind, assess_session

_LABEL = {
    Status.PASS: "PASS",
    Status.WARN: "WARN",
    Status.FAIL: "FAIL",
    Status.UNKNOWN: "UNKNOWN",
    Status.NOT_APPLICABLE: "N/A",
    Status.NOT_TESTED: "NOT TESTED",
}
_STYLE = {
    Status.PASS: "green",
    Status.WARN: "yellow",
    Status.FAIL: "red bold",
    Status.UNKNOWN: "magenta",
}
_DETAILED = (Status.WARN, Status.FAIL, Status.UNKNOWN)


def headline(snapshot: Snapshot) -> str:
    """``Session: Wayland | Desktop: GNOME | Portal: 1.21.1+ds-1``."""
    parts = []
    if snapshot.session is not None:
        facts = snapshot.session
        kind = assess_session(facts.environment, facts.paths, facts.logind).kind
        parts.append(f"Session: {_KIND.get(kind, kind.value)}")
    services = snapshot.services
    env = services.activation_environment if services else None
    if env is None and snapshot.session is not None:
        env = snapshot.session.environment
    if env is not None:
        identity = identify_desktop(env)
        bundle = bundle_for(identity.family)
        name = bundle.name if bundle is not None else identity.name
        parts.append(f"Desktop: {name or env.current_desktop or 'unknown'}")
    version = portal_version(snapshot)
    if version:
        parts.append(f"Portal: {version}")
    return " | ".join(parts)


_KIND = {SessionKind.WAYLAND: "Wayland", SessionKind.X11: "X11", SessionKind.NONE: "none"}


def render_findings(snapshot: Snapshot, console: Console, *, show_all: bool = False) -> None:
    """Every finding on one line, with reason, next step and check for the ones that need it.

    Findings that follow from another reported one are hidden unless ``show_all``, so a
    single root cause is not shown as a cascade.
    """
    console.print(Text(f"screenshare-doctor {snapshot.tool_version}", style="bold"))
    line = headline(snapshot)
    if line:
        console.print(Text(line))
    console.print()
    shown = snapshot.findings if show_all else root_causes(snapshot.findings)
    hidden = len(snapshot.findings) - len(shown)
    for finding in shown:
        _render_one(finding, console)
    if hidden:
        console.print()
        console.print(
            Text(
                (
                    f"{hidden} more finding(s) follow from the ones above and are not shown "
                    "(--all shows them)."
                ),
                style="dim",
            )
        )
    counts = Counter(f.status for f in snapshot.findings)
    console.print()
    summary = ", ".join(
        f"{counts.get(status, 0)} {label.lower()}"
        for status, label in (
            (Status.PASS, "pass"),
            (Status.WARN, "warn"),
            (Status.FAIL, "fail"),
            (Status.UNKNOWN, "unknown"),
        )
    )
    console.print(Text(f"Summary: {summary}", style="bold"))
    if snapshot.probe_failures:
        console.print(Text("Could not check:", style="bold"))
        for failure in snapshot.probe_failures:
            console.print(Text(f"  {failure.probe}: {failure.detail}"))
    console.print(
        Text(
            "Nothing was started, changed or recorded; no screen-sharing request was made.",
            style="dim",
        )
    )
    redactions = redaction_line(snapshot)
    if redactions:
        console.print(Text(redactions, style="dim"))


def _render_one(finding: Finding, console: Console) -> None:
    label = _LABEL[finding.status]
    summary = finding.summary
    if finding.caused_by:
        summary += f" (follows from {finding.caused_by})"
    console.print(
        Text.assemble(
            (f"{label:<8}", _STYLE.get(finding.status, "dim")),
            (f"{finding.id:<19}", "bold"),
            summary,
        )
    )
    if finding.status not in _DETAILED:
        return
    indent = " " * 27
    console.print(Text(f"{indent}{finding.reason}"))
    if finding.recommended_action:
        console.print(Text(f"{indent}Next: {finding.recommended_action}"))
    if finding.verify_command:
        console.print(Text(f"{indent}Check: {finding.verify_command}"))
    for limitation in finding.limitations:
        console.print(Text(f"{indent}Note: {limitation}", style="dim"))
