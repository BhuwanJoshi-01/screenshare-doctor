from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from screenshare_doctor.screencast import cursor_mode_names, source_type_names


@pytest.mark.parametrize(
    ("mask", "names"),
    [
        (7, ("monitor", "window", "virtual")),
        (1, ("monitor",)),
        (3, ("monitor", "window")),
        (0, ()),
        (9, ("monitor", "bit 3")),
    ],
)
def test_source_types(mask: int, names: tuple[str, ...]) -> None:
    assert source_type_names(mask) == names


def test_cursor_modes() -> None:
    assert cursor_mode_names(7) == ("hidden", "embedded", "metadata")
    assert cursor_mode_names(2) == ("embedded",)


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_every_set_bit_is_named_once(mask: int) -> None:
    assert len(source_type_names(mask)) == mask.bit_count()
