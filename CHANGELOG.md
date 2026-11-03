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
- `screenshare-doctor doctor [--strict] [--all]`: every check from the session
  to PipeWire (15 checks, `SSD-*` codes, listed in `docs/rules.md`), with
  evidence, the next step and a command to verify it. Findings that follow
  from another are folded under their root cause. `--strict` exits 1 on any
  failure.
- `screenshare-doctor rules list` and `rules explain CODE`.
- `screenshare-doctor troubleshoot screenshare [--app NAME] [--symptom
  SYMPTOM] [--explain]`: the checks that explain one of five symptoms
  (`no-picker`, `black-screen`, `missing-window`, `permission-denied`,
  `app-only`), most likely cause first, with sourced hints for Firefox, the
  Chromium family, Electron apps and OBS, and Flatpak detection
  (`docs/apps-and-symptoms.md`).
- `doctor --format json` and `report [--format markdown|json] [--output FILE]
  [--force]`: the redacted report as an issue-ready Markdown document or as
  JSON frozen in `docs/json-schema-v1.json`, with a derived `summary` (session,
  desktop, portal version, counts, worst status). Contract tests keep the code
  and the schema in step and prove that planted secrets reach no output.
