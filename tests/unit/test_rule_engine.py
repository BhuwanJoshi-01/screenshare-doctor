"""The rule engine: registration, evaluation order, broken rules, root causes."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from screenshare_doctor.models import Confidence, Finding, Layer, Severity, Snapshot, Status
from screenshare_doctor.rules.engine import Registry, RuleContext, evaluate, root_causes

SNAPSHOT = Snapshot(tool_version="0.1.0", created_at="2026-11-03T10:00:00Z")


def _finding(rule_id: str, status: Status = Status.PASS, **extra: object) -> Finding:
    return Finding(
        id=rule_id,
        status=status,
        severity=Severity.INFO,
        confidence=Confidence.HIGH,
        summary=f"{rule_id} checked",
        reason="because",
        **extra,  # type: ignore[arg-type]
    )


def test_rules_run_in_registration_order_with_their_layer() -> None:
    registry = Registry()

    @registry.rule("SSD-TEST-002", "second registered first", layer=Layer.DBUS)
    def first(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Explains the first rule."""
        yield _finding("SSD-TEST-002")

    @registry.rule("SSD-TEST-001", "first registered second", layer=Layer.SESSION)
    def second(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Explains the second rule."""
        yield _finding("SSD-TEST-001", layer=Layer.APP)

    findings = evaluate(SNAPSHOT, registry)
    assert [(f.id, f.layer) for f in findings] == [
        ("SSD-TEST-002", Layer.DBUS),
        ("SSD-TEST-001", Layer.APP),  # a finding may name its own layer
    ]
    assert len(registry) == 2
    rule = registry.get("ssd-test-002")
    assert rule is not None
    assert rule.explanation == "Explains the first rule."


def test_a_broken_rule_becomes_unknown_and_the_others_still_run() -> None:
    registry = Registry()

    @registry.rule("SSD-TEST-001", "broken", layer=Layer.PIPEWIRE)
    def broken(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Always fails."""
        raise KeyError("boom")

    @registry.rule("SSD-TEST-002", "fine", layer=Layer.SESSION)
    def fine(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Always passes."""
        yield _finding("SSD-TEST-002")

    first, second = evaluate(SNAPSHOT, registry)
    assert (first.id, first.status, first.layer) == ("SSD-TEST-001", Status.UNKNOWN, Layer.PIPEWIRE)
    assert "KeyError" in first.reason
    assert second.status is Status.PASS


def test_a_rule_may_not_report_under_another_code() -> None:
    registry = Registry()

    @registry.rule("SSD-TEST-001", "liar", layer=Layer.SESSION)
    def liar(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Reports someone else's code."""
        yield _finding("SSD-TEST-002")

    with pytest.raises(ValueError, match="reported a finding as SSD-TEST-002"):
        evaluate(SNAPSHOT, registry)


@pytest.mark.parametrize("bad_id", ["GSI-SYS-001", "SSD-TEST-1", "ssd-test-001"])
def test_rule_ids_must_be_ssd_codes(bad_id: str) -> None:
    with pytest.raises(ValueError, match="does not match"):
        Registry().rule(bad_id, "x", layer=Layer.SESSION)(lambda s, c: ())


def test_duplicate_and_undocumented_rules_are_rejected() -> None:
    registry = Registry()

    def documented(snapshot: Snapshot, context: RuleContext) -> Iterator[Finding]:
        """Documented."""
        yield from ()

    registry.rule("SSD-TEST-001", "x", layer=Layer.SESSION)(documented)
    with pytest.raises(ValueError, match="registered twice"):
        registry.rule("SSD-TEST-001", "x", layer=Layer.SESSION)(documented)
    with pytest.raises(ValueError, match="no docstring"):
        registry.rule("SSD-TEST-002", "x", layer=Layer.SESSION)(lambda s, c: ())


def test_root_causes_fold_findings_under_their_reported_cause() -> None:
    bus = _finding("SSD-DBUS-001", Status.FAIL)
    portal = _finding("SSD-PORTAL-001", Status.UNKNOWN, caused_by="SSD-DBUS-001")
    orphan = _finding("SSD-PORTAL-002", Status.UNKNOWN, caused_by="SSD-PW-001")
    assert root_causes([bus, portal, orphan]) == (bus, orphan)
