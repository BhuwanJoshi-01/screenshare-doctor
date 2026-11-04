# Screenshare Doctor

**Find out why screen sharing fails on your Linux Wayland desktop.**

[![CI](https://github.com/BhuwanJoshi-01/screenshare-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/BhuwanJoshi-01/screenshare-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/LICENSE)
[![Website](https://img.shields.io/badge/website-screenshare--doctor-1b1d24.svg)](https://bhuwanjoshi-01.github.io/screenshare-doctor/)

> **Status:** 0.1.0 is the first release, tested on real GNOME, KDE Plasma and Hyprland sessions. Reports from
> other setups are very welcome; see the [roadmap](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/roadmap.md) for what comes next.

You click "Share screen" in a browser or a meeting app and get a black frame, no picker, the wrong windows or a
permission error. The cause can sit in the app, the way it was launched (native, Flatpak, XWayland), the
xdg-desktop-portal routing, the desktop's portal backend, PipeWire, WirePlumber or the compositor. Screenshare
Doctor starts from **the app and the symptom** and tells you which layer is most likely at fault, with the evidence:

![troubleshoot output for Discord with no picker on GNOME: every portal check passes except SSD-PORTAL-002, ScreenCast is disabled by a portals.conf in the user's config folder, and the running portal still uses its old configuration until it is restarted; the most likely cause is named with the restart command.](https://raw.githubusercontent.com/BhuwanJoshi-01/screenshare-doctor/main/docs/images/troubleshoot.svg)

## Install

Needs Python 3.11 or newer and a Linux desktop session to diagnose.

```bash
uv tool install screenshare-doctor
pipx install screenshare-doctor          # or with pipx
```

## Use

```bash
screenshare-doctor troubleshoot screenshare --app firefox --symptom no-picker
screenshare-doctor routes explain ScreenCast     # which portal backend handles screen sharing, and why
screenshare-doctor report --output screenshare-report.md   # redacted, safe to paste
```

It is tested on real GNOME, KDE Plasma and Hyprland sessions. A desktop is listed as supported only after such a
test.

What works already (see the [command reference](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/cli.md)):

- `screenshare-doctor troubleshoot screenshare --app firefox --symptom no-picker` starts from the app and what
  you see, and shows the checks that explain it, most likely cause first ([apps and symptoms](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/apps-and-symptoms.md)).
- `screenshare-doctor doctor` runs every [check](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/rules.md), from the session to PipeWire, and explains what
  needs attention; `--format json` for scripts ([JSON output](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/json-output.md)).
- `screenshare-doctor report --output screenshare-report.md` writes a redacted report to paste into a bug tracker.
- `screenshare-doctor check session` tells Wayland, X11, SSH and no session apart and shows the desktop names the
  portal reads.
- `screenshare-doctor check services` shows which portal backends, PipeWire and WirePlumber are installed and
  running, and whether portals will see the same desktop variables as your shell.
- `screenshare-doctor check dbus` shows which portal services are on the session bus and what they offer for
  screen sharing, without starting any of them.
- `screenshare-doctor check desktop` compares your setup with what GNOME, KDE Plasma, Hyprland or wlroots ship by
  default ([the defaults and their sources](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/desktops.md)).
- `screenshare-doctor routes explain ScreenCast` names the backend the portal picks, the line of the
  `portals.conf` that decides it, and whether the bus agrees, using the rules of your portal version
  ([how routing works](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/portal-routing.md)).

## What it promises

- **Passive by default.** No command opens a screen-sharing request or picker, records anything, starts,
  restarts or stops a service, or changes configuration. A portal that isn't running is reported as such, not
  started. Testing a real screen-sharing request (planned for 0.2) is a separate command that asks first.
- **No root.** It never needs `sudo`.
- **Configured vs observed.** The report says whether a backend is *predicted* by your `portals.conf` files or
  *observed* answering on D-Bus.
- **Unknown is not a pass.** A check that could not run is shown as unknown, never as green.
- **Shareable reports.** User names, home paths and window titles are redacted before any output is written,
  JSON included. No network access, no telemetry.

## GNOME Shell extension

A small top-bar indicator shows the result of `doctor` whenever you open its menu; see
[extension/README.md](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/extension/README.md). It needs the command-line tool and runs nothing while the menu is closed.

## Tested on

Real Wayland sessions of GNOME 50.1 (Ubuntu 26.04), KDE Plasma 6.8.2 (Fedora 45, in a VM) and Hyprland 0.57.1 (Arch
Linux, in a VM). wlroots compositors such as sway are covered by upstream defaults only. See the
[support matrix](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/support-matrix.md) and [privacy](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/privacy.md).

## Alternatives

- [PortalDoctor](https://github.com/SetraTheXX/Portal-Doctor) offers thorough read-only portal, D-Bus and PipeWire
  diagnostics, validated on GNOME.
- [wayland-cast-doctor](https://github.com/ljm-233/wayland-cast-doctor) checks the session, the ScreenCast backend
  and PipeWire.

Screenshare Doctor focuses on the **app-centred workflow** and on validated GNOME, KDE and Hyprland coverage.

## Documentation

[Command reference](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/cli.md) · [Troubleshooting](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/troubleshooting.md) · [Checks](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/rules.md) ·
[Portal routing](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/portal-routing.md) · [Desktop defaults](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/desktops.md) ·
[Apps and symptoms](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/apps-and-symptoms.md) · [Privacy](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/privacy.md) · [Support matrix](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/support-matrix.md) ·
[JSON output](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/json-output.md) · [Architecture](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/architecture.md) · [Sample reports](https://github.com/BhuwanJoshi-01/screenshare-doctor/tree/main/docs/sample-reports) ·
[Roadmap](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/docs/roadmap.md)

## License

The CLI is [MIT](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/LICENSE). The GNOME Shell extension is [GPL-2.0-or-later](https://github.com/BhuwanJoshi-01/screenshare-doctor/blob/main/extension/LICENSE).
