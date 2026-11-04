# Screen sharing report

Session: Wayland \| Desktop: KDE Plasma \| Portal: 1.22.1-2.fc45

screenshare-doctor 0.1.0, 2026-11-04T04:17:35Z. 14 pass, 0 warn, 0 fail, 0 unknown.

## Checks

| Status | Code | Layer | Finding |
| --- | --- | --- | --- |
| PASS | `SSD-SESSION-001` | session | Wayland session |
| PASS | `SSD-SESSION-002` | session | The Wayland display is reachable |
| PASS | `SSD-SESSION-003` | session | The portal reads the desktop names kde |
| PASS | `SSD-SESSION-004` | session | Portals see the same desktop and display |
| PASS | `SSD-DBUS-001` | dbus | The session bus answers |
| PASS | `SSD-PKG-001` | portal-frontend | xdg-desktop-portal 1.22.1-2.fc45 is installed |
| PASS | `SSD-SERVICE-001` | portal-frontend | xdg-desktop-portal.service is active |
| PASS | `SSD-PORTAL-001` | portal-frontend | The portal frontend offers ScreenCast (version 6) |
| PASS | `SSD-PORTAL-002` | portal-backend | ScreenCast goes to the kde backend, which runs |
| PASS | `SSD-PORTAL-003` | portal-frontend | Every portal file found is read |
| PASS | `SSD-PORTAL-004` | portal-backend | ScreenCast offers monitor, window, virtual |
| PASS | `SSD-DESKTOP-001` | portal-backend | The setup matches KDE Plasma's defaults |
| N/A | `SSD-COMPOSITOR-001` | compositor | the compositor offers screen casts |
| PASS | `SSD-PW-001` | pipewire | PipeWire 1.6.11 answers |
| PASS | `SSD-WP-001` | wireplumber | WirePlumber is connected to PipeWire |

## Facts

| Fact | Value |
| --- | --- |
| XDG\_SESSION\_TYPE | `wayland` |
| XDG\_CURRENT\_DESKTOP | `KDE` |
| WAYLAND\_DISPLAY | `wayland-1` |
| DISPLAY | `:0` |
| XDG\_CURRENT\_DESKTOP (user manager) | `KDE` |
| WAYLAND\_DISPLAY (user manager) | `wayland-1` |
| package xdg-desktop-portal | `1.22.1-2.fc45` |
| package xdg-desktop-portal-gnome | `not installed` |
| package xdg-desktop-portal-gtk | `1.15.3-6.fc45` |
| package xdg-desktop-portal-kde | `6.8.2-1.fc45` |
| package xdg-desktop-portal-wlr | `not installed` |
| package xdg-desktop-portal-hyprland | `not installed` |
| package pipewire | `1.6.11-1.fc45` |
| package wireplumber | `0.5.19-1.fc45` |
| PipeWire | `1.6.11` |

---

Made by [screenshare-doctor](https://github.com/BhuwanJoshi-01/screenshare-doctor), read-only: nothing was started, changed or recorded. Redacted from this output: 6 home paths.
