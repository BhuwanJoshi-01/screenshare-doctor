# Screen sharing report

Session: Wayland \| Desktop: GNOME \| Portal: 1.21.1+ds-1ubuntu3.1

screenshare-doctor 0.1.0, 2026-11-03T12:00:00Z. 15 pass, 0 warn, 0 fail, 0 unknown.

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
| PASS | `SSD-PORTAL-002` | portal-backend | ScreenCast goes to the gnome backend, which runs |
| PASS | `SSD-PORTAL-003` | portal-frontend | Every portal file found is read |
| PASS | `SSD-PORTAL-004` | portal-backend | ScreenCast offers monitor, window, virtual |
| PASS | `SSD-DESKTOP-001` | portal-backend | The setup matches GNOME's defaults |
| PASS | `SSD-COMPOSITOR-001` | compositor | org.gnome.Mutter.ScreenCast is running |
| PASS | `SSD-PW-001` | pipewire | PipeWire 1.6.2 answers |
| PASS | `SSD-WP-001` | wireplumber | WirePlumber is connected to PipeWire |

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

Made by [screenshare-doctor](https://github.com/BhuwanJoshi-01/screenshare-doctor), read-only: nothing was started, changed or recorded. Redacted from this output: 7 home paths.
