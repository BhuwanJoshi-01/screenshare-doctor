"""Reading the portal files in search order (WLD-005)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from screenshare_doctor.collectors.portal_config import (
    MAX_FILE_BYTES,
    collect_portal_files,
    list_portal_files,
    read_capped,
)
from screenshare_doctor.models import FailureKind, XdgDirectories
from tests.fakes import FIXTURES

UBUNTU_DIRS = XdgDirectories(
    home="/home/u",
    config_dirs="/etc/xdg/xdg-ubuntu:/etc/xdg",
    data_dirs="/usr/share/ubuntu:/usr/share/gnome:/usr/local/share/:/usr/share/",
)


def rooted(root: Path) -> tuple[Callable[[str], bytes | None], Callable[[str], tuple[str, ...]]]:
    """read and list_dir functions that see ``root`` as ``/``."""
    return (
        lambda path: read_capped(str(root) + path),
        lambda path: list_portal_files(str(root) + path),
    )


def install(root: Path, path: str, data: bytes) -> None:
    target = root / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


@pytest.fixture
def ubuntu_root(tmp_path: Path) -> Path:
    """The real Ubuntu 26.04 portal files under a temporary root."""
    share = "/usr/share/xdg-desktop-portal"
    install(
        tmp_path,
        f"{share}/gnome-portals.conf",
        (FIXTURES / "portals" / "gnome-portals.conf").read_bytes(),
    )
    for name in ("gnome.portal", "gtk.portal", "gnome-keyring.portal"):
        install(tmp_path, f"{share}/portals/{name}", (FIXTURES / "portals" / name).read_bytes())
    return tmp_path


def test_real_ubuntu_layout(ubuntu_root: Path) -> None:
    read, list_dir = rooted(ubuntu_root)
    files, failures = collect_portal_files(
        ("ubuntu", "gnome"), UBUNTU_DIRS, read=read, list_dir=list_dir
    )
    assert failures == ()
    # /usr/share is both in XDG_DATA_DIRS and DATADIR; a second search finds nothing new.
    assert [c.path for c in files.configs] == ["/usr/share/xdg-desktop-portal/gnome-portals.conf"]
    assert [d.source for d in files.descriptors] == ["gnome-keyring", "gnome", "gtk"]
    assert files.desktops == ("ubuntu", "gnome")
    assert files.unreadable == ()


def test_desktop_specific_file_comes_before_portals_conf(tmp_path: Path) -> None:
    install(
        tmp_path, "/home/u/.config/xdg-desktop-portal/portals.conf", b"[preferred]\ndefault=gtk\n"
    )
    install(
        tmp_path,
        "/home/u/.config/xdg-desktop-portal/gnome-portals.conf",
        b"[preferred]\ndefault=gnome\n",
    )
    read, list_dir = rooted(tmp_path)
    files, _ = collect_portal_files(
        ("gnome",), XdgDirectories(home="/home/u"), read=read, list_dir=list_dir
    )
    assert [c.path.rsplit("/", 1)[1] for c in files.configs] == [
        "gnome-portals.conf",
        "portals.conf",
    ]


def test_unreadable_file_is_recorded(tmp_path: Path) -> None:
    def denied(path: str) -> bytes | None:
        if path.endswith("gnome-portals.conf"):
            raise PermissionError(13, "Permission denied", path)
        return None

    files, failures = collect_portal_files(
        ("gnome",), XdgDirectories(home="/home/u"), read=denied, list_dir=lambda d: ()
    )
    assert files.configs == ()
    assert "/home/u/.config/xdg-desktop-portal/gnome-portals.conf" in files.unreadable
    assert failures[0].kind is FailureKind.PERMISSION_DENIED
    assert "Permission denied" in failures[0].detail


def test_oversized_file_is_not_parsed(tmp_path: Path) -> None:
    install(tmp_path, "/etc/xdg-desktop-portal/portals.conf", b"#" * (MAX_FILE_BYTES + 1))
    read, list_dir = rooted(tmp_path)
    files, failures = collect_portal_files((), XdgDirectories(), read=read, list_dir=list_dir)
    assert files.configs == ()
    assert files.unreadable == ("/etc/xdg-desktop-portal/portals.conf",)
    assert "larger than 64 KiB" in failures[0].detail


def test_unlistable_descriptor_directory(tmp_path: Path) -> None:
    def broken(directory: str) -> tuple[str, ...]:
        raise PermissionError(13, "Permission denied", directory)

    files, failures = collect_portal_files(
        (), XdgDirectories(), read=lambda p: None, list_dir=broken
    )
    assert files.descriptors == ()
    assert len(files.unreadable) == len(files.descriptor_directories)
    assert all(f.kind is FailureKind.PERMISSION_DENIED for f in failures)


def test_portal_dir_override(tmp_path: Path) -> None:
    install(tmp_path, "/srv/test/portals.conf", b"[preferred]\ndefault=test\n")
    install(
        tmp_path,
        "/srv/test/test.portal",
        b"[portal]\nDBusName=org.freedesktop.impl.portal.Test\nInterfaces=org.freedesktop.impl.portal.ScreenCast\n",
    )
    read, list_dir = rooted(tmp_path)
    files, _ = collect_portal_files(
        ("gnome",), XdgDirectories(portal_dir="/srv/test"), read=read, list_dir=list_dir
    )
    assert files.config_directories == ("/srv/test",)
    assert [c.path for c in files.configs] == ["/srv/test/portals.conf"]
    assert [d.source for d in files.descriptors] == ["test"]


def test_only_portal_files_are_listed(tmp_path: Path) -> None:
    (tmp_path / "gnome.portal").write_text("")
    (tmp_path / "README").write_text("")
    (tmp_path / "x.portal.bak").write_text("")
    assert list_portal_files(str(tmp_path)) == ("gnome.portal",)
    assert list_portal_files(str(tmp_path / "missing")) == ()


def test_read_capped_on_missing_and_file_parent(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("x")
    assert read_capped(str(tmp_path / "missing")) is None
    assert read_capped(str(tmp_path / "file" / "portals.conf")) is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
def test_read_capped_permission_error(tmp_path: Path) -> None:
    target = tmp_path / "portals.conf"
    target.write_text("[preferred]\n")
    target.chmod(0)
    with pytest.raises(PermissionError):
        read_capped(str(target))
