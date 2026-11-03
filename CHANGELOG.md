# Changelog

All notable changes to this project are listed here. Versions follow
[Semantic Versioning](https://semver.org/); the JSON report format has its own
`schema_version` and changes only with a new major version of the schema.

## Unreleased

Nothing released yet. The first release (0.1.0) will diagnose screen sharing
read-only, on GNOME first, then KDE Plasma and Hyprland.

- `screenshare-doctor --help` and `--version`. Exit codes: 0 when the
  diagnosis ran (whatever it found), 1 for `--strict` failures, 2 for usage
  errors and internal errors, 3 when required context (a graphical session)
  is missing, 130 for Ctrl+C. Internal errors print one redacted line;
  `SSD_DEBUG=1` shows the traceback.
- `screenshare-doctor check session`: the session type (Wayland, X11, none),
  where the tool runs (desktop, SSH, text console, elsewhere), the desktop as
  xdg-desktop-portal reads `XDG_CURRENT_DESKTOP`, the display sockets and
  logind's view of the user's graphical session, with notes on anything that
  does not add up. Reads an allowlist of session variables, `stat()`s the
  sockets and runs `loginctl show-*` only. Exits 3 without a graphical session.
