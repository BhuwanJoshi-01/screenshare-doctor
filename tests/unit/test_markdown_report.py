"""Markdown output (WLD-008)."""

from __future__ import annotations

import dataclasses

import pytest

from screenshare_doctor.models import (
    Confidence,
    DbusFacts,
    Evidence,
    Finding,
    RedactionCount,
    Severity,
    Snapshot,
    Status,
)
from screenshare_doctor.orchestrator import diagnose
from screenshare_doctor.reports.markdown import cell_code, code, render_markdown, text
from tests.unit.test_json_report import real_snapshot


def test_real_machine_report() -> None:
    out = render_markdown(real_snapshot())
    assert out.startswith("# Screen sharing report\n")
    assert "Session: Wayland \\| Desktop: GNOME \\| Portal: 1.21.1+ds-1ubuntu3.1" in out
    assert "15 pass, 0 warn, 0 fail, 0 unknown." in out
    assert "| PASS | `SSD-SESSION-001` | session | Wayland session |" in out
    assert "What needs attention" not in out
    assert "| XDG\\_CURRENT\\_DESKTOP (user manager) | `ubuntu:GNOME` |" in out
    assert "| package xdg-desktop-portal-kde | `not installed` |" in out
    assert out.endswith("nothing was started, changed or recorded.\n")


def test_problems_get_their_own_section_with_evidence() -> None:
    snapshot = diagnose(dataclasses.replace(real_snapshot(), dbus=DbusFacts(reachable=False)))
    out = render_markdown(snapshot)
    assert "## What needs attention" in out
    assert "### FAIL `SSD-DBUS-001`: The session bus does not answer" in out
    assert "**Check afterwards:** `busctl --user status`" in out
    assert "(follows from `SSD-DBUS-001`)" in out
    assert "### UNKNOWN `SSD-PORTAL-001`" not in out  # folded under its root cause


def test_hostile_values_cannot_break_the_markdown() -> None:
    finding = Finding(
        "SSD-PORTAL-003",
        Status.WARN,
        Severity.LOW,
        Confidence.HIGH,
        summary="<script>alert(1)</script> | # [x](javascript:y)",
        reason="a`b``c",
        evidence=(Evidence("portal file", "path", "/srv/``weird``|name"),),
    )
    out = render_markdown(Snapshot(tool_version="0.1.0", created_at="x", findings=(finding,)))
    assert "<script>" not in out
    assert "\\<script\\>" in out
    assert "\\| \\# \\[x\\](javascript:y)" in out
    # Fenced longer than the content, and the pipe escaped so the table cell holds.
    assert "| ```/srv/``weird``\\|name``` |" in out


@pytest.mark.parametrize(
    ("raw", "fenced"),
    [
        ("plain", "`plain`"),
        ("a`b", "``a`b``"),
        ("`edge`", "`` `edge` ``"),
        ("multi\nline", "`multi line`"),
    ],
)
def test_code_spans(raw: str, fenced: str) -> None:
    assert code(raw) == fenced


def test_text_flattens_and_escapes() -> None:
    assert text("a\n  b_c *d*") == "a b\\_c \\*d\\*"


def test_redactions_are_named_in_the_footer() -> None:
    snapshot = Snapshot(
        tool_version="0.1.0", created_at="x", redactions=(RedactionCount("home_path", 3),)
    )
    assert "Redacted from this output: 3 home paths." in render_markdown(snapshot)


def test_cell_code_escapes_pipes() -> None:
    assert cell_code("a|b") == "`a\\|b`"
