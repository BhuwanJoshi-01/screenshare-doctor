"""busctl --json=short output (WLD-004)."""

from __future__ import annotations

import contextlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.dbus import (
    BusctlOutputError,
    parse_bool_reply,
    parse_busctl_json,
    parse_string_list_reply,
)
from tests.fakes import read_fixture


def test_real_name_has_owner_replies() -> None:
    assert parse_bool_reply(read_fixture("busctl", "name-has-owner-true.json")) is True
    assert parse_bool_reply(read_fixture("busctl", "name-has-owner-false.json")) is False


def test_real_activatable_names() -> None:
    names = parse_string_list_reply(read_fixture("busctl", "list-activatable-ubuntu-gnome.json"))
    assert "org.freedesktop.portal.Desktop" in names
    assert "org.freedesktop.impl.portal.desktop.gnome" in names
    assert "org.freedesktop.impl.portal.desktop.kde" not in names


def test_several_documents_one_per_line() -> None:
    text = '{"type":"u","data":5}\n{"type":"u","data":7}\n'
    assert [d["data"] for d in parse_busctl_json(text)] == [5, 7]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "u 5\n",
        '{"type":"b"}\n',
        "[1, 2]\n",
        '{"type":"b","data":[tru\n',
    ],
)
def test_malformed_output_is_an_error(text: str) -> None:
    with pytest.raises(BusctlOutputError):
        parse_busctl_json(text)


@pytest.mark.parametrize(
    "text",
    [
        '{"type":"s","data":["yes"]}',
        '{"type":"b","data":[1]}',
        '{"type":"b","data":[true,false]}',
        '{"type":"b","data":true}',
    ],
)
def test_bool_reply_must_be_one_boolean(text: str) -> None:
    with pytest.raises(BusctlOutputError):
        parse_bool_reply(text)


@pytest.mark.parametrize(
    "text",
    ['{"type":"as","data":[[1]]}', '{"type":"as","data":["a"]}', '{"type":"s","data":[[]]}'],
)
def test_string_list_reply_must_be_one_string_array(text: str) -> None:
    with pytest.raises(BusctlOutputError):
        parse_string_list_reply(text)


@given(st.text())
def test_parsers_raise_only_their_own_error(text: str) -> None:
    for parse in (parse_busctl_json, parse_bool_reply, parse_string_list_reply):
        with contextlib.suppress(BusctlOutputError):
            parse(text)
