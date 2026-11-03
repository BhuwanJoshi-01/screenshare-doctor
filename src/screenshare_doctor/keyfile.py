"""A reader for the GLib key-file format used by ``.portal`` files and ``portals.conf``.

xdg-desktop-portal reads both with GLib's ``GKeyFile``, so this follows its rules
where they decide which backend is picked:

- Blank lines and lines starting with ``#`` are ignored; leading whitespace is too.
- ``[Group]`` starts a group; a repeated group continues the earlier one.
- ``Key=Value``: whitespace before ``=`` is dropped, spaces after it too. A key that is
  set twice keeps its **last** value (GKeyFile's lookup table is replaced), which is
  why the portal warns about a duplicate ``default`` key.
- ``Key[locale]=…`` translations are skipped.
- Anything else, or a key before the first group, makes the whole file unreadable,
  as ``g_key_file_load_from_file`` fails and the portal ignores the file.
- Lists are separated by ``;``, a trailing ``;`` is optional, ``\\;`` is a literal
  semicolon, and ``\\s``, ``\\n``, ``\\t``, ``\\r``, ``\\\\`` are the usual escapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_ESCAPES = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}


class KeyFileError(ValueError):
    """The file is not a valid key file, or a value has an invalid escape."""


@dataclass(frozen=True)
class KeyFile:
    """The groups of a key file; values are kept raw (escapes not yet applied)."""

    groups: dict[str, dict[str, str]] = field(default_factory=dict)
    duplicates: tuple[tuple[str, str], ...] = ()
    """``(group, key)`` pairs that were set more than once (the last value counts)."""

    def has_group(self, group: str) -> bool:
        return group in self.groups

    def keys(self, group: str) -> tuple[str, ...]:
        """The keys of ``group`` in the order they first appear."""
        return tuple(self.groups.get(group, {}))

    def get_string(self, group: str, key: str) -> str | None:
        raw = self.groups.get(group, {}).get(key)
        return None if raw is None else _unescape(raw)

    def get_string_list(self, group: str, key: str) -> tuple[str, ...] | None:
        raw = self.groups.get(group, {}).get(key)
        return None if raw is None else split_list(raw)


def parse_keyfile(data: bytes) -> KeyFile:
    """Parse key-file bytes; raises :class:`KeyFileError` where GKeyFile would fail."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KeyFileError(f"not valid UTF-8 at byte {exc.start}") from None
    groups: dict[str, dict[str, str]] = {}
    duplicates: list[tuple[str, str]] = []
    current: str | None = None
    for number, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.removesuffix("\r").lstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if not line.endswith("]") or len(line) < 3 or any(c in line[1:-1] for c in "[]"):
                raise KeyFileError(f"line {number}: invalid group header")
            current = line[1:-1]
            groups.setdefault(current, {})
            continue
        key, equals, value = line.partition("=")
        key = key.rstrip()
        if not equals or not key:
            raise KeyFileError(f"line {number}: not a group, key or comment")
        if current is None:
            raise KeyFileError(f"line {number}: key before the first group")
        if "[" in key:
            if not key.endswith("]"):
                raise KeyFileError(f"line {number}: invalid key {key!r}")
            continue  # a translation
        group = groups[current]
        if key in group:
            duplicates.append((current, key))
        group[key] = value.lstrip(" ")
    return KeyFile(groups, tuple(duplicates))


def split_list(raw: str) -> tuple[str, ...]:
    """Split a raw list value on unescaped ``;`` and unescape each item."""
    items: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "\\" and index + 1 < len(raw) and raw[index + 1] == ";":
            current.append(r"\;")
            index += 2
            continue
        if char == ";":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    if current:
        items.append("".join(current))
    return tuple(_unescape(item, in_list=True) for item in items)


def _unescape(raw: str, *, in_list: bool = False) -> str:
    out: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        if index + 1 >= len(raw):
            raise KeyFileError("value ends with a lone backslash")
        escaped = raw[index + 1]
        if escaped in _ESCAPES:
            out.append(_ESCAPES[escaped])
        elif in_list and escaped == ";":
            out.append(";")
        else:
            raise KeyFileError(f"invalid escape \\{escaped}")
        index += 2
    return "".join(out)
