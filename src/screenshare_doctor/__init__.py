"""Screenshare Doctor: find out why screen sharing fails on Linux Wayland desktops."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("screenshare-doctor")
except PackageNotFoundError:  # imported from a source tree that was never installed
    __version__ = "0+unknown"
