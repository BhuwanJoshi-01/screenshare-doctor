"""The GKeyFile subset that portal files use."""

from __future__ import annotations

import contextlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.keyfile import KeyFileError, parse_keyfile, split_list
from tests.fakes import FIXTURES


def test_real_gnome_portals_conf() -> None:
    keyfile = parse_keyfile((FIXTURES / "portals" / "gnome-portals.conf").read_bytes())
    assert keyfile.keys("preferred") == ("default", "org.freedesktop.impl.portal.Secret")
    assert keyfile.get_string_list("preferred", "default") == ("gnome", "gtk")


def test_real_gnome_portal_descriptor() -> None:
    keyfile = parse_keyfile((FIXTURES / "portals" / "gnome.portal").read_bytes())
    assert keyfile.get_string("portal", "DBusName") == "org.freedesktop.impl.portal.desktop.gnome"
    interfaces = keyfile.get_string_list("portal", "Interfaces")
    assert interfaces is not None
    assert "org.freedesktop.impl.portal.ScreenCast" in interfaces
    assert keyfile.get_string_list("portal", "UseIn") == ("gnome",)


@pytest.mark.parametrize(
    ("raw", "items"),
    [
        ("gnome;gtk;", ("gnome", "gtk")),
        ("gnome;gtk", ("gnome", "gtk")),
        ("gnome", ("gnome",)),
        ("", ()),
        (";", ("",)),
        ("a;;b", ("a", "", "b")),
        (r"a\;b;c", ("a;b", "c")),
        ("a\\sb", ("a b",)),
        ("gnome ;gtk", ("gnome ", "gtk")),
    ],
)
def test_split_list(raw: str, items: tuple[str, ...]) -> None:
    assert split_list(raw) == items


def test_last_duplicate_key_wins_and_is_reported() -> None:
    keyfile = parse_keyfile(b"[preferred]\ndefault=gnome\ndefault=kde\n")
    assert keyfile.get_string_list("preferred", "default") == ("kde",)
    assert keyfile.duplicates == (("preferred", "default"),)
    assert keyfile.keys("preferred") == ("default",)


def test_repeated_groups_are_merged() -> None:
    keyfile = parse_keyfile(b"[preferred]\na=1\n[other]\nb=2\n[preferred]\nc=3\n")
    assert keyfile.keys("preferred") == ("a", "c")


def test_comments_blank_lines_whitespace_and_crlf() -> None:
    data = b"# comment\r\n\r\n  [preferred]\r\n  default = gnome;\r\n"
    assert parse_keyfile(data).get_string_list("preferred", "default") == ("gnome",)


def test_translations_are_skipped() -> None:
    keyfile = parse_keyfile(b"[portal]\nName=x\nName[de]=y\n")
    assert keyfile.keys("portal") == ("Name",)


@pytest.mark.parametrize(
    "data",
    [
        b"default=gnome\n",  # key before any group
        b"[preferred]\nthis is not a pair\n",
        b"[preferred\ndefault=gnome\n",
        b"[]\n",
        b"[a]b]\n",
        b"[preferred]\n=gnome\n",
        b"[preferred]\nkey[de=x\n",
        b"[preferred]\ndefault=\xff\n",
    ],
)
def test_files_the_portal_cannot_load(data: bytes) -> None:
    with pytest.raises(KeyFileError):
        parse_keyfile(data)


@pytest.mark.parametrize("raw", ["bad\\q", "ends\\"])
def test_invalid_escapes(raw: str) -> None:
    keyfile = parse_keyfile(f"[g]\nk={raw}\n".encode())
    with pytest.raises(KeyFileError):
        keyfile.get_string("g", "k")


def test_missing_group_or_key() -> None:
    keyfile = parse_keyfile(b"[preferred]\n")
    assert keyfile.get_string("preferred", "default") is None
    assert keyfile.get_string_list("portal", "Interfaces") is None
    assert keyfile.keys("portal") == ()
    assert keyfile.has_group("preferred")


_item = st.text(
    alphabet=st.characters(blacklist_characters=r"\;", blacklist_categories=("Cs",)), min_size=1
)


@given(st.lists(_item, min_size=1, max_size=6))  # ";" alone is one empty item
def test_lists_round_trip(items: list[str]) -> None:
    assert split_list(";".join(items) + ";") == tuple(items)


@given(st.binary())
def test_parser_raises_only_its_own_error(data: bytes) -> None:
    with contextlib.suppress(KeyFileError):
        parse_keyfile(data)
