"""XDG_CURRENT_DESKTOP parsing (WLD-001)."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.desktops import DesktopList, ascii_lower, parse_desktop_list


@pytest.mark.parametrize(
    ("raw", "names"),
    [
        ("ubuntu:GNOME", ("ubuntu", "gnome")),
        ("GNOME", ("gnome",)),
        ("KDE", ("kde",)),
        ("Hyprland", ("hyprland",)),
        ("Budgie:GNOME", ("budgie", "gnome")),
        ("X-Cinnamon", ("x-cinnamon",)),
        ("GNOME-Classic:GNOME", ("gnome-classic", "gnome")),
        ("sway", ("sway",)),
        ("::GNOME:", ("gnome",)),
        ("", ()),
        (None, ()),
    ],
)
def test_parse_desktop_list(raw: str | None, names: tuple[str, ...]) -> None:
    assert parse_desktop_list(raw) == DesktopList(names)


def test_order_is_kept_most_specific_first() -> None:
    assert parse_desktop_list("pop:GNOME").names == ("pop", "gnome")


@pytest.mark.parametrize(
    ("raw", "names", "ignored"),
    [
        ("ubuntu: GNOME", ("ubuntu",), (" GNOME",)),
        ("GNOME;KDE", (), ("GNOME;KDE",)),
        ("gnome/../x", (), ("gnome/../x",)),
        ("Ägypten:KDE", ("kde",), ("Ägypten",)),
        ("GNOME\n", (), ("GNOME\n",)),
    ],
)
def test_entries_the_portal_ignores_are_reported_as_found(
    raw: str, names: tuple[str, ...], ignored: tuple[str, ...]
) -> None:
    # The portal skips these because it builds file names from desktop names; hiding them
    # would hide why gnome-portals.conf is never read.
    assert parse_desktop_list(raw) == DesktopList(names, ignored)


def test_only_ascii_letters_are_lowered() -> None:
    assert ascii_lower("GNOME-Ä") == "gnome-Ä"


@given(st.text())
def test_names_are_valid_lower_case_file_name_parts(raw: str) -> None:
    for name in parse_desktop_list(raw).names:
        assert re.fullmatch(r"[a-z0-9_-]+", name)


@given(st.text())
def test_every_non_empty_entry_is_either_used_or_ignored(raw: str) -> None:
    parsed = parse_desktop_list(raw)
    entries = [entry for entry in raw.split(":") if entry]
    assert len(parsed.names) + len(parsed.ignored) == len(entries)


@given(st.lists(st.from_regex(r"[A-Za-z0-9_-]{1,16}", fullmatch=True), max_size=5))
def test_valid_lists_round_trip(names: list[str]) -> None:
    assert parse_desktop_list(":".join(names)) == DesktopList(tuple(n.lower() for n in names))


_ASCII_UPPER = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


@given(st.text())
def test_names_ignore_ascii_case(raw: str) -> None:
    assert parse_desktop_list(raw.translate(_ASCII_UPPER)).names == parse_desktop_list(raw).names
