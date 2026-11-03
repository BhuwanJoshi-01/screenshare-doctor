"""Names for the ScreenCast bit masks, as the portal specification defines them."""

from __future__ import annotations

SOURCE_TYPES: tuple[tuple[int, str], ...] = ((1, "monitor"), (2, "window"), (4, "virtual"))
CURSOR_MODES: tuple[tuple[int, str], ...] = ((1, "hidden"), (2, "embedded"), (4, "metadata"))


def flag_names(mask: int, flags: tuple[tuple[int, str], ...]) -> tuple[str, ...]:
    """The names of the bits set in ``mask``; unknown bits become ``bit N``.

    A newer portal may define more bits than this list; they are shown rather than
    dropped, so nothing it reports is hidden.
    """
    names = [name for bit, name in flags if mask & bit]
    known = sum(bit for bit, _ in flags)
    unknown = mask & ~known
    position = 0
    while unknown:
        if unknown & 1:
            names.append(f"bit {position}")
        unknown >>= 1
        position += 1
    return tuple(names)


def source_type_names(mask: int) -> tuple[str, ...]:
    return flag_names(mask, SOURCE_TYPES)


def cursor_mode_names(mask: int) -> tuple[str, ...]:
    return flag_names(mask, CURSOR_MODES)
