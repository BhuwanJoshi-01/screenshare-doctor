# Screen sharing report

Session: Wayland \| Desktop: GNOME \| Portal: 1.21.1+ds-1ubuntu3.1

screenshare-doctor 0.1.0, 2026-11-03T12:00:00Z. 13 pass, 0 warn, 2 fail, 0 unknown.

## Checks

| Status | Code | Layer | Finding |
| --- | --- | --- | --- |
| PASS | `SSD-SESSION-001` | session | Wayland session |
| PASS | `SSD-SESSION-002` | session | The Wayland display is reachable |
| PASS | `SSD-SESSION-003` | session | The portal reads the desktop names ubuntu, gnome |
| PASS | `SSD-SESSION-004` | session | Portals see the same desktop and display |
| PASS | `SSD-DBUS-001` | dbus | The session bus answers |
| PASS | `SSD-PKG-001` | portal-frontend | xdg-desktop-portal 1.21.1+ds-1ubuntu3.1 is installed |
| PASS | `SSD-SERVICE-001` | portal-frontend | xdg-desktop-portal.service is active |
| PASS | `SSD-PORTAL-001` | portal-frontend | The portal frontend offers ScreenCast (version 5) |
| FAIL | `SSD-PORTAL-002` | portal-backend | ScreenCast is disabled by a portals.conf |
| PASS | `SSD-PORTAL-003` | portal-frontend | Every portal file found is read |
| PASS | `SSD-PORTAL-004` | portal-backend | ScreenCast offers monitor, window, virtual |
| FAIL | `SSD-DESKTOP-001` | portal-backend | The setup differs from GNOME's defaults |
| PASS | `SSD-COMPOSITOR-001` | compositor | org.gnome.Mutter.ScreenCast is running |
| PASS | `SSD-PW-001` | pipewire | PipeWire 1.6.2 answers |
| PASS | `SSD-WP-001` | wireplumber | WirePlumber is connected to PipeWire |

## What needs attention

### FAIL `SSD-PORTAL-002`: ScreenCast is disabled by a portals.conf

~/.config/xdg-desktop-portal/portals.conf sets it to none. The running portal still offers ScreenCast: it reads its configuration only when it starts, so it was started before this changed and keeps the old choice until it is restarted.

| Source | Fact | Value |
| --- | --- | --- |
| route | backend | not reported |
| route | decided by | `~/.config/xdg-desktop-portal/portals.conf` |
| busctl | agreement | `offered_without_backend` |

**Next step:** Remove the none entry from ~/.config/xdg-desktop-portal/portals.conf if it was not meant to disable screen sharing. Restart the portal afterwards: systemctl --user restart xdg-desktop-portal.service

**Check afterwards:** `screenshare-doctor routes explain ScreenCast`

### FAIL `SSD-DESKTOP-001`: The setup differs from GNOME's defaults

ScreenCast is routed to the gnome backend - fail (ScreenCast is disabled by ~/.config/xdg-desktop-portal/portals.conf)

| Source | Fact | Value |
| --- | --- | --- |
| GNOME default | xdg-desktop-portal-gnome is installed | `version 50.0-0ubuntu1 (pass)` |
| GNOME default | gnome.portal declares ScreenCast | `/usr/share/xdg-desktop-portal/portals/gnome.portal (pass)` |
| GNOME default | gnome-portals.conf is installed | `/usr/share/xdg-desktop-portal/gnome-portals.conf (pass)` |
| GNOME default | ScreenCast is routed to the gnome backend | `ScreenCast is disabled by ~/.config/xdg-desktop-portal/portals.conf (fail)` |
| GNOME default | org.freedesktop.impl.portal.desktop.gnome runs or can be started | `running (pass)` |

**Next step:** See why ScreenCast is not routed: screenshare-doctor routes explain ScreenCast

**Check afterwards:** `screenshare-doctor check desktop`

## Facts

| Fact | Value |
| --- | --- |
| XDG\_SESSION\_TYPE | `wayland` |
| XDG\_CURRENT\_DESKTOP | `ubuntu:GNOME` |
| WAYLAND\_DISPLAY | `wayland-0` |
| DISPLAY | `:0` |
| XDG\_CURRENT\_DESKTOP (user manager) | `ubuntu:GNOME` |
| WAYLAND\_DISPLAY (user manager) | `wayland-0` |
| package xdg-desktop-portal | `1.21.1+ds-1ubuntu3.1` |
| package xdg-desktop-portal-gnome | `50.0-0ubuntu1` |
| package xdg-desktop-portal-gtk | `1.15.3-2ubuntu1` |
| package xdg-desktop-portal-kde | `not installed` |
| package xdg-desktop-portal-wlr | `not installed` |
| package xdg-desktop-portal-hyprland | `not installed` |
| package pipewire | `1.6.2-1ubuntu1.2` |
| package wireplumber | `0.5.13-1ubuntu1.1` |
| PipeWire | `1.6.2` |

---

Made by [screenshare-doctor](https://github.com/BhuwanJoshi-01/screenshare-doctor), read-only: nothing was started, changed or recorded. Redacted from this output: 13 home paths.
