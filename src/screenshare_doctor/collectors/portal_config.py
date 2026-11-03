"""Read the portal configuration files, in the frontend's search order.

Only the candidate ``(DESKTOP-)portals.conf`` files and the ``*.portal`` files of the
search directories are opened, read-only and at most :data:`MAX_FILE_BYTES` each. Their
contents are parsed at once and only the parsed fields are kept.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from screenshare_doctor.models import (
    FailureKind,
    PortalDescriptor,
    PortalFiles,
    PortalsConf,
    ProbeFailure,
    XdgDirectories,
)
from screenshare_doctor.portal_files import parse_descriptor, parse_portals_conf
from screenshare_doctor.portal_paths import (
    config_candidates,
    config_directories,
    descriptor_directories,
    join,
)

MAX_FILE_BYTES = 64 * 1024
"""Real files are a few hundred bytes; anything this large is not a portal file."""


class FileTooLargeError(OSError):
    """A file is larger than :data:`MAX_FILE_BYTES`."""


def read_capped(path: str) -> bytes | None:
    """The file's bytes, ``None`` if it does not exist; raises ``OSError`` otherwise."""
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        return None
    except NotADirectoryError:
        return None  # a path component is a file: the portal finds nothing there either
    if len(data) > MAX_FILE_BYTES:
        raise FileTooLargeError(f"larger than {MAX_FILE_BYTES // 1024} KiB")
    return data


def list_portal_files(directory: str) -> tuple[str, ...]:
    """Names ending in ``.portal`` in ``directory``, sorted; empty if it is missing."""
    try:
        return tuple(
            sorted(e.name for e in Path(directory).iterdir() if e.name.endswith(".portal"))
        )
    except (FileNotFoundError, NotADirectoryError):
        return ()


def collect_portal_files(
    desktops: Sequence[str],
    dirs: XdgDirectories,
    *,
    read: Callable[[str], bytes | None] = read_capped,
    list_dir: Callable[[str], tuple[str, ...]] = list_portal_files,
    variables_from: str = "user manager",
) -> tuple[PortalFiles, tuple[ProbeFailure, ...]]:
    """Every portals.conf candidate and .portal file the frontend would consider."""
    failures: list[ProbeFailure] = []
    unreadable: list[str] = []

    def load(path: str) -> bytes | None:
        try:
            return read(path)
        except OSError as exc:
            unreadable.append(path)
            reason = exc.strerror or str(exc)
            failures.append(ProbeFailure("portal files", _kind(exc), f"{path}: {reason}"))
            return None

    names = tuple(desktops)
    config_dirs = config_directories(dirs)
    configs: list[PortalsConf] = []
    for directory in config_dirs:
        for path in config_candidates(directory, names):
            data = load(path)
            if data is not None:
                configs.append(parse_portals_conf(path, data))

    descriptor_dirs = descriptor_directories(dirs)
    descriptors: list[PortalDescriptor] = []
    for directory in descriptor_dirs:
        try:
            names_in_dir = list_dir(directory)
        except OSError as exc:
            unreadable.append(directory)
            failures.append(
                ProbeFailure("portal files", _kind(exc), f"{directory}: {exc.strerror or exc}")
            )
            continue
        for name in names_in_dir:
            path = join(directory, name)
            data = load(path)
            if data is not None:
                descriptors.append(parse_descriptor(path, data))

    found = PortalFiles(
        desktops=names,
        config_directories=config_dirs,
        configs=tuple(configs),
        descriptor_directories=descriptor_dirs,
        descriptors=tuple(descriptors),
        unreadable=tuple(unreadable),
        variables_from=variables_from,
    )
    return found, tuple(failures)


def _kind(exc: OSError) -> FailureKind:
    if isinstance(exc, PermissionError):
        return FailureKind.PERMISSION_DENIED
    if isinstance(exc, FileTooLargeError):
        return FailureKind.MALFORMED_OUTPUT
    return FailureKind.OS_ERROR
