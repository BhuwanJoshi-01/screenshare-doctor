"""Rules: pure functions from a snapshot to findings, registered under stable codes."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace

from screenshare_doctor.models import (
    FINDING_ID,
    Confidence,
    Finding,
    Layer,
    Severity,
    Snapshot,
    Status,
)


@dataclass(frozen=True, slots=True)
class RuleContext:
    """What the user told the tool, which changes how some facts are judged.

    ``app`` and ``symptom`` come from ``troubleshoot screenshare --app … --symptom …``;
    ``None`` means a general check.
    """

    app: str | None = None
    symptom: str | None = None


RuleCheck = Callable[[Snapshot, RuleContext], Iterable[Finding]]


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    title: str
    layer: Layer
    explanation: str
    check: RuleCheck
    sources: tuple[str, ...] = ()


class Registry:
    """Rules in registration order, which is the order they are evaluated and listed."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def rule(
        self, rule_id: str, title: str, *, layer: Layer, sources: Iterable[str] = ()
    ) -> Callable[[RuleCheck], RuleCheck]:
        """Register a check; its docstring becomes the explanation shown by ``rules explain``."""

        def register(check: RuleCheck) -> RuleCheck:
            if not FINDING_ID.fullmatch(rule_id):
                raise ValueError(f"rule id {rule_id!r} does not match SSD-<AREA>-<NNN>")
            if rule_id in self._rules:
                raise ValueError(f"rule {rule_id} is registered twice")
            explanation = inspect.cleandoc(check.__doc__ or "")
            if not explanation:
                raise ValueError(f"rule {rule_id} has no docstring to explain it")
            self._rules[rule_id] = Rule(rule_id, title, layer, explanation, check, tuple(sources))
            return check

        return register

    def __iter__(self) -> Iterator[Rule]:
        return iter(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id.upper())


def evaluate(
    snapshot: Snapshot, rules: Iterable[Rule], context: RuleContext | None = None
) -> tuple[Finding, ...]:
    """Run every rule in order and collect their findings.

    A rule may only report findings under its own code, and each finding gets the
    rule's layer unless it names one itself. A rule that raises is a bug in this tool;
    it becomes an ``unknown`` finding for that check instead of hiding every other
    result, and never a pass.
    """
    context = context or RuleContext()
    findings: list[Finding] = []
    for rule in rules:
        try:
            produced = list(rule.check(snapshot, context))
        except Exception as exc:  # report the broken check, keep the others
            findings.append(_internal_error(rule, exc))
            continue
        for finding in produced:
            if finding.id != rule.id:
                raise ValueError(f"rule {rule.id} reported a finding as {finding.id}")
            if finding.layer is None:
                finding = _with_layer(finding, rule.layer)
            findings.append(finding)
    return tuple(findings)


def _with_layer(finding: Finding, layer: Layer) -> Finding:
    return replace(finding, layer=layer)


def _internal_error(rule: Rule, exc: Exception) -> Finding:
    return Finding(
        id=rule.id,
        status=Status.UNKNOWN,
        severity=Severity.LOW,
        confidence=Confidence.LOW,
        summary=f"{rule.title}: not checked because of an internal error",
        reason=f"The check failed with {type(exc).__name__}: {exc}",
        layer=rule.layer,
        recommended_action="Please report this as a bug, with the redacted report.",
    )


def root_causes(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """The findings that do not follow from another reported finding.

    A finding with ``caused_by`` is folded under its cause when the cause is among the
    findings, so a report shows "the session bus is unreachable" once instead of a
    cascade of portal and backend failures.
    """
    items = tuple(findings)
    reported = {finding.id for finding in items}
    return tuple(f for f in items if f.caused_by is None or f.caused_by not in reported)
