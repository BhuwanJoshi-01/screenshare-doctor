"""Pick and order the findings that matter for one app and one symptom.

Pure function of the findings and the profiles: the symptom decides which checks are
relevant and in which order; the app adds sourced hints; nothing is re-checked.
"""

from __future__ import annotations

from dataclasses import dataclass

from screenshare_doctor.models import Finding, Status
from screenshare_doctor.rules.engine import root_causes
from screenshare_doctor.troubleshoot import AppProfile, AppProfiles, Hint, Symptom

_PROBLEMS = (Status.FAIL, Status.WARN, Status.UNKNOWN)


@dataclass(frozen=True, slots=True)
class Troubleshooting:
    """The answer to "why does screen sharing fail in this app with this symptom".

    ``relevant`` are the symptom's checks in its order (all checks without a symptom),
    with findings that follow from a reported root cause folded away. ``likely`` is the
    first relevant failure, else warning, else unknown. ``others`` are problems outside
    the symptom's checks, which may still matter.
    """

    symptom: Symptom | None
    app_name: str | None
    app: AppProfile | None
    flatpak: tuple[str, ...]
    relevant: tuple[Finding, ...]
    likely: Finding | None
    others: tuple[Finding, ...]
    hints: tuple[Hint, ...]


def troubleshoot(
    findings: tuple[Finding, ...],
    *,
    symptom: Symptom | None,
    app_name: str | None,
    apps: AppProfiles,
    flatpak: tuple[str, ...] = (),
) -> Troubleshooting:
    folded = root_causes(findings)
    if symptom is None:
        relevant = folded
        others: tuple[Finding, ...] = ()
    else:
        by_id = {finding.id: finding for finding in folded}
        relevant = tuple(by_id[code] for code in symptom.rules if code in by_id)
        others = tuple(f for f in folded if f.id not in symptom.rules and f.status in _PROBLEMS)
    likely = None
    for status in _PROBLEMS:
        likely = next((f for f in relevant if f.status is status), None)
        if likely is not None:
            break
    app = apps.find(app_name) if app_name else None
    hints = app.hints_for(symptom.id if symptom else None) if app else ()
    if flatpak:
        hints = (*hints, apps.flatpak)
    return Troubleshooting(symptom, app_name, app, flatpak, relevant, likely, others, hints)
