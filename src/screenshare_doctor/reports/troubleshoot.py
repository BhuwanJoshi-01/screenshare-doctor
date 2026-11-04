"""Terminal output of ``troubleshoot screenshare``.

Collected text is added as plain ``Text``, never as Rich markup.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from screenshare_doctor.models import Snapshot, Status
from screenshare_doctor.reports.findings import headline, render_finding
from screenshare_doctor.reports.terminal import redaction_line
from screenshare_doctor.rules.engine import Registry
from screenshare_doctor.troubleshoot.select import Troubleshooting

_NOT_RUN = (Status.NOT_TESTED, Status.UNKNOWN)


def render_troubleshooting(
    snapshot: Snapshot,
    result: Troubleshooting,
    rules: Registry,
    console: Console,
    *,
    explain: bool = False,
) -> None:
    """The symptom's checks in order, the likely cause, the app's hints and the rest."""
    who = result.app.name if result.app else (result.app_name or "any app")
    what = result.symptom.title if result.symptom else "every check"
    console.print(Text(f"screenshare-doctor {snapshot.tool_version}: {who}: {what}", style="bold"))
    line = headline(snapshot)
    if line:
        console.print(Text(line))
    if result.symptom is not None:
        console.print()
        console.print(Text(result.symptom.explanation))
    console.print()
    console.print(
        Text("Checked, most likely cause first:" if result.symptom else "Checked:", style="bold")
    )
    for finding in result.relevant:
        render_finding(finding, console, details=explain)
        if explain:
            rule = rules.get(finding.id)
            if rule is not None:
                for paragraph in rule.explanation.split("\n\n"):
                    console.print(Text(" " * 27 + " ".join(paragraph.split()), style="dim"))
    console.print()
    if result.likely is not None:
        console.print(
            Text.assemble(("Most likely: ", "bold"), f"{result.likely.id}: {result.likely.summary}")
        )
    elif not_run := [f.id for f in result.relevant if f.status in _NOT_RUN]:
        console.print(
            Text(
                f"{len(not_run)} of these checks could not run ({', '.join(not_run)}); the others "
                "found no problem. Run them as their Next step says before looking at the app."
            )
        )
    else:
        console.print(
            Text(
                "None of these checks found a problem. The cause is probably in the app itself; "
                "the hints below may help.",
            )
        )
    if result.app_name and result.app is None:
        console.print()
        console.print(
            Text(
                f"No profile for {result.app_name!r}; the checks above apply to any app.",
                style="dim",
            )
        )
    if result.hints:
        console.print()
        console.print(Text(f"About {result.app.name if result.app else 'this app'}:", style="bold"))
        if result.flatpak:
            console.print(Text(f"  Installed as a Flatpak: {', '.join(result.flatpak)}"))
        for hint in result.hints:
            console.print(Text(f"  - {hint.text}"))
            console.print(
                Text(f"    Source ({hint.confidence} confidence): {hint.source}", style="dim")
            )
    if result.others:
        console.print()
        console.print(Text("Other problems found, outside this symptom:", style="bold"))
        for finding in result.others:
            render_finding(finding, console)
    if result.symptom is not None and result.symptom.limitations:
        console.print()
        for limitation in result.symptom.limitations:
            console.print(Text(f"Not checked: {limitation}", style="dim"))
    console.print()
    console.print(
        Text(
            "Nothing was started, changed or recorded; no screen-sharing request was made.",
            style="dim",
        )
    )
    redactions = redaction_line(snapshot)
    if redactions:
        console.print(Text(redactions, style="dim"))
