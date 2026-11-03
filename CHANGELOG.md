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
- `screenshare-doctor check services`: the installed portal frontend, backends,
  PipeWire and WirePlumber (from dpkg, rpm or pacman, or their programs when
  there is no package manager), the state of their user services, and the
  environment the user manager starts portals in, compared with the shell's.
  Query commands only; nothing is started.
- `screenshare-doctor check dbus`: which portal services run on the session
  bus or could start, and the ScreenCast version, source types and cursor
  modes of the running ones. Only the bus daemon and already-running services
  are asked, with `busctl --auto-start=no`, so nothing is started. Exits 3
  when the session bus cannot be reached.
- `screenshare-doctor routes explain [INTERFACE]`: which backend
  xdg-desktop-portal picks for ScreenCast (or any interface), the entry and
  file that decide it, every configuration directory in search order, and
  whether the bus agrees. Applies the selection rules of the installed portal
  version (they changed in 1.17, 1.19, 1.20.1 and 1.21.1; see
  `docs/portal-routing.md`).
- `check services` also shows the PipeWire daemon: version, whether
  WirePlumber, xdg-desktop-portal and the compositor are connected, how many
  other clients there are, and video node counts. `pw-dump` runs only when
  `pipewire.service` is already active, because connecting to a
  socket-activated PipeWire would start it.
- `screenshare-doctor check desktop [--as gnome|kde|hyprland|wlroots]`:
  compares the backend package, its `.portal` file, the desktop's
  `portals.conf`, the ScreenCast route, the backend on the bus and (on GNOME)
  Mutter's screen-cast service with what the desktop ships by default. The
  defaults and their upstream sources are in `docs/desktops.md`.
