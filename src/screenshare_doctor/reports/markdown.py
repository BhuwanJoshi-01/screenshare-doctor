"""Markdown output: an issue-ready report of an already redacted snapshot.

Collected text is escaped so a path containing ``|`` cannot break a table and ``<tag>``
cannot become HTML in an issue tracker; values go in code spans whose fence is longer
than any backtick run they contain.
"""

from __future__ import annotations

import re
from collections import Counter

from screenshare_doctor.models import Finding, Snapshot, Status
from screenshare_doctor.reports.findings import headline
from screenshare_doctor.reports.terminal import redaction_line
from screenshare_doctor.rules.engine import root_causes

PROJECT_URL = "https://github.com/BhuwanJoshi-01/screenshare-doctor"
_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")
_PROBLEMS = (Status.FAIL, Status.WARN, Status.UNKNOWN)
_LABEL = {
    Status.FAIL: "FAIL",
    Status.WARN: "WARN",
    Status.UNKNOWN: "UNKNOWN",
    Status.PASS: "PASS",
    Status.NOT_APPLICABLE: "N/A",
    Status.NOT_TESTED: "NOT TESTED",
}


def text(value: str) -> str:
    """Plain text that Markdown and HTML will not interpret; one line."""
    return _SPECIAL.sub(r"\\\1", " ".join(value.split()))


def code(value: str) -> str:
    """An inline code span that survives any backticks inside the value."""
    flat = " ".join(value.split())
    longest = max((len(run) for run in re.findall(r"`+", flat)), default=0)
    fence = "`" * (longest + 1)
    padding = " " if flat.startswith("`") or flat.endswith("`") else ""
    return f"{fence}{padding}{flat}{padding}{fence}"


def cell_code(value: str) -> str:
    """A code span for a table cell: GitHub splits cells at ``|`` even inside code spans
    unless it is escaped, and renders ``\\|`` there as a plain pipe."""
    return code(value).replace("|", "\\|")


def render_markdown(snapshot: Snapshot) -> str:
    """The report: summary, findings table, details of what needs attention, facts."""
    lines: list[str] = ["# Screen sharing report", ""]
    line = headline(snapshot)
    if line:
        lines += [text(line), ""]
    counts = Counter(f.status for f in snapshot.findings)
    lines += [
        f"screenshare-doctor {text(snapshot.tool_version)}, {text(snapshot.created_at)}. "
        f"{counts.get(Status.PASS, 0)} pass, {counts.get(Status.WARN, 0)} warn, "
        f"{counts.get(Status.FAIL, 0)} fail, {counts.get(Status.UNKNOWN, 0)} unknown.",
        "",
    ]
    if snapshot.findings:
        lines += [
            "## Checks",
            "",
            "| Status | Code | Layer | Finding |",
            "| --- | --- | --- | --- |",
        ]
        for finding in snapshot.findings:
            summary = text(finding.summary)
            if finding.caused_by:
                summary += f" (follows from {code(finding.caused_by)})"
            layer = finding.layer.value if finding.layer else "—"
            lines.append(f"| {_LABEL[finding.status]} | {code(finding.id)} | {layer} | {summary} |")
        lines.append("")
        problems = [f for f in root_causes(snapshot.findings) if f.status in _PROBLEMS]
        if problems:
            lines += ["## What needs attention", ""]
            for finding in problems:
                lines += _details(finding)
    lines += _facts(snapshot)
    if snapshot.probe_failures:
        lines += ["## Could not check", ""]
        lines += [f"- {code(f.probe)}: {text(f.detail)}" for f in snapshot.probe_failures]
        lines.append("")
    footer = redaction_line(snapshot)
    closing = (
        f"Made by [screenshare-doctor]({PROJECT_URL}), read-only: "
        "nothing was started, changed or recorded."
    )
    if footer:
        closing += f" {text(footer)}."
    lines += ["---", "", closing, ""]
    return "\n".join(lines)


def _details(finding: Finding) -> list[str]:
    title = f"### {_LABEL[finding.status]} {code(finding.id)}: {text(finding.summary)}"
    lines = [title, "", text(finding.reason), ""]
    if finding.evidence:
        lines += ["| Source | Fact | Value |", "| --- | --- | --- |"]
        for item in finding.evidence:
            value = cell_code(item.value) if item.value is not None else "not reported"
            lines.append(f"| {text(item.source)} | {text(item.key)} | {value} |")
        lines.append("")
    if finding.recommended_action:
        lines += [f"**Next step:** {text(finding.recommended_action)}", ""]
    if finding.verify_command:
        lines += [f"**Check afterwards:** {code(finding.verify_command)}", ""]
    for limitation in finding.limitations:
        lines += [f"*Note:* {text(limitation)}", ""]
    return lines


def _facts(snapshot: Snapshot) -> list[str]:
    rows: list[tuple[str, str | None]] = []
    if snapshot.session is not None:
        env = snapshot.session.environment
        rows += [
            ("XDG_SESSION_TYPE", env.session_type),
            ("XDG_CURRENT_DESKTOP", env.current_desktop),
            ("WAYLAND_DISPLAY", env.wayland_display),
            ("DISPLAY", env.display),
        ]
    services = snapshot.services
    if services is not None and services.activation_environment is not None:
        activation = services.activation_environment
        rows += [
            ("XDG_CURRENT_DESKTOP (user manager)", activation.current_desktop),
            ("WAYLAND_DISPLAY (user manager)", activation.wayland_display),
        ]
    for package in snapshot.packages.packages if snapshot.packages else ():
        value = package.version if package.version else package.state.value.replace("_", " ")
        rows.append((f"package {package.name}", value))
    if snapshot.pipewire is not None and snapshot.pipewire.version:
        rows.append(("PipeWire", snapshot.pipewire.version))
    if not rows:
        return []
    lines = ["## Facts", "", "| Fact | Value |", "| --- | --- |"]
    lines += [
        f"| {text(name)} | {cell_code(value) if value else 'unset'} |" for name, value in rows
    ]
    lines.append("")
    return lines
