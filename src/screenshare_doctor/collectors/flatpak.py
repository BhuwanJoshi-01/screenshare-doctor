"""Whether an app is installed as a Flatpak, from the installation directories only.

``stat()`` of ``/var/lib/flatpak/app/<id>`` (system) and
``~/.local/share/flatpak/app/<id>`` (user); flatpak itself is not run, and only the
ids of the app being troubleshot are looked up.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

SYSTEM_DIR = "/var/lib/flatpak/app"
USER_SUBDIR = ".local/share/flatpak/app"


def _is_dir(path: str) -> bool:
    return Path(path).is_dir()


def installed_flatpaks(
    ids: Sequence[str], *, home: str | None, is_dir: Callable[[str], bool] = _is_dir
) -> tuple[str, ...]:
    """The ids among ``ids`` that are installed system-wide or for the user."""
    roots = [SYSTEM_DIR] + ([f"{home.rstrip('/')}/{USER_SUBDIR}"] if home else [])
    return tuple(app_id for app_id in ids if any(is_dir(f"{root}/{app_id}") for root in roots))
