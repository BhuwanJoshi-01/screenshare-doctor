"""pw-dump output, reduced to counters."""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.collectors.pipewire import (
    PwDumpError,
    client_summary,
    core_version,
    parse_pw_dump,
    video_summary,
)
from tests.fakes import read_fixture


def test_real_core() -> None:
    assert (
        core_version(parse_pw_dump(read_fixture("pipewire", "pw-dump-core-ubuntu.json"))) == "1.6.2"
    )


def test_real_clients() -> None:
    known, others = client_summary(
        parse_pw_dump(read_fixture("pipewire", "pw-dump-clients-ubuntu.json"))
    )
    assert known == ("Mutter", "WirePlumber", "gnome-shell", "xdg-desktop-portal")
    assert others == 12  # media keys, volume control, browsers, chat… only counted


def test_real_nodes() -> None:
    nodes = parse_pw_dump(read_fixture("pipewire", "pw-dump-nodes-ubuntu.json"))
    assert video_summary(nodes) == (1, 0, 0)  # the webcam, no screen cast


def test_screen_cast_stream_and_source() -> None:
    nodes = [
        {"type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Video/Source"}}},
        {
            "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Stream/Input/Video"}},
        },
        {"type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Audio/Sink"}}},
    ]
    assert video_summary(nodes) == (0, 1, 1)


def test_application_names_are_never_returned() -> None:
    objects = [
        {
            "type": "PipeWire:Interface:Client",
            "info": {"props": {"application.name": "Secret Meeting App"}},
        },
        {
            "type": "PipeWire:Interface:Client",
            "info": {"props": {"application.name": "WirePlumber"}},
        },
    ]
    known, others = client_summary(objects)
    assert known == ("WirePlumber",)
    assert others == 1
    assert "Secret" not in repr((known, others))


def test_odd_objects_are_tolerated() -> None:
    objects = [
        {"type": "PipeWire:Interface:Client"},
        {"type": "PipeWire:Interface:Client", "info": None},
        {"type": "PipeWire:Interface:Node", "info": {"props": []}},
        {"type": "PipeWire:Interface:Core", "info": {"version": 7}},
    ]
    assert client_summary(objects) == ((), 2)
    assert video_summary(objects) == (0, 0, 0)
    assert core_version(objects) is None


@pytest.mark.parametrize("text", ["", "{}", "[1, 2]", "[{]"])
def test_malformed_dumps(text: str) -> None:
    with pytest.raises(PwDumpError):
        parse_pw_dump(text)


@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.text(),
        lambda c: st.lists(c) | st.dictionaries(st.text(), c),
        max_leaves=20,
    )
)
def test_summaries_never_raise_on_any_json(value: object) -> None:
    text = json.dumps([value] if isinstance(value, dict) else value)
    try:
        objects = parse_pw_dump(text)
    except PwDumpError:
        return
    client_summary(objects)
    video_summary(objects)
    core_version(objects)
