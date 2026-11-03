# Screenshare Doctor

**Find out why screen sharing fails on your Linux Wayland desktop.**

> **Status: in development.** Nothing is released yet. The commands below are the planned interface for 0.1.0;
> see the [roadmap](docs/roadmap.md).

You click "Share screen" in a browser or a meeting app and get a black frame, no picker, the wrong windows or a
permission error. The cause can sit in the app, the way it was launched (native, Flatpak, XWayland), the
xdg-desktop-portal routing, the desktop's portal backend, PipeWire, WirePlumber or the compositor. Screenshare
Doctor starts from **the app and the symptom** and tells you which layer is most likely at fault, with the evidence:

```bash
screenshare-doctor troubleshoot screenshare --app firefox --symptom no-picker
screenshare-doctor routes explain ScreenCast     # which portal backend handles screen sharing, and why
screenshare-doctor report --format markdown --output screenshare-report.md   # redacted, safe to paste
```

GNOME comes first, then KDE Plasma and Hyprland. A desktop is listed as supported only after a test on a real
session.

What works already (see the [command reference](docs/cli.md)):

- `screenshare-doctor doctor` runs every [check](docs/rules.md), from the session to PipeWire, and explains what
  needs attention.
- `screenshare-doctor check session` tells Wayland, X11, SSH and no session apart and shows the desktop names the
  portal reads.
- `screenshare-doctor check services` shows which portal backends, PipeWire and WirePlumber are installed and
  running, and whether portals will see the same desktop variables as your shell.
- `screenshare-doctor check dbus` shows which portal services are on the session bus and what they offer for
  screen sharing, without starting any of them.
- `screenshare-doctor check desktop` compares your setup with what GNOME, KDE Plasma, Hyprland or wlroots ship by
  default ([the defaults and their sources](docs/desktops.md)).
- `screenshare-doctor routes explain ScreenCast` names the backend the portal picks, the line of the
  `portals.conf` that decides it, and whether the bus agrees, using the rules of your portal version
  ([how routing works](docs/portal-routing.md)).

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

## Alternatives

- [PortalDoctor](https://github.com/SetraTheXX/Portal-Doctor) offers thorough read-only portal, D-Bus and PipeWire
  diagnostics, validated on GNOME.
- [wayland-cast-doctor](https://github.com/ljm-233/wayland-cast-doctor) checks the session, the ScreenCast backend
  and PipeWire.

Screenshare Doctor focuses on the **app-centred workflow** and on validated GNOME, KDE and Hyprland coverage.

## License

The CLI is [MIT](LICENSE). The GNOME Shell extension (once added) is GPL-2.0-or-later.
