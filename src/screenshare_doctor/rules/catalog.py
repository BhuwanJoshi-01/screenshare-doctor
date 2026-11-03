"""The built-in rules. Modules register into RULES when imported, in evaluation order."""

from __future__ import annotations

import importlib

from screenshare_doctor.rules.engine import Registry

RULES = Registry()

_MODULES: tuple[str, ...] = ("session",)
"""Evaluation order, from the session up to the app, as a screen-sharing request
travels. Kept as data on purpose: import sorting would otherwise reorder the rules."""


def builtin_rules() -> Registry:
    """All built-in rules, in evaluation order."""
    for name in _MODULES:
        importlib.import_module(f"screenshare_doctor.rules.{name}")
    return RULES
