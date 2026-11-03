# Checks

`screenshare-doctor doctor` runs every check below, in this order: from the session up to PipeWire, the way a
screen-sharing request travels. `screenshare-doctor rules explain CODE` prints a check's full explanation.

Statuses: **PASS** the check ran and the facts are as needed; **WARN** something differs and may be the cause, or may
be deliberate; **FAIL** the facts show screen sharing cannot work this way; **UNKNOWN** the facts could not be read
(never a pass); **N/A** the check does not apply here. A finding can *follow from* another (for example every portal
check from an unreachable session bus); `doctor` then shows only the root cause unless you pass `--all`.

| Code | Layer | Checks |
| --- | --- | --- |
| `SSD-SESSION-001` | session | The desktop session is Wayland (X11 warns, no graphical session fails) |
| `SSD-SESSION-002` | session | Apps started here can reach the Wayland display (stale socket fails; XWayland-only shell warns) |
| `SSD-SESSION-003` | session | The portal's `XDG_CURRENT_DESKTOP` names the desktop, without entries the portal drops |
| `SSD-SESSION-004` | session | The user manager, which starts the portals, has the session's `WAYLAND_DISPLAY` and `XDG_CURRENT_DESKTOP` |
| `SSD-DBUS-001` | dbus | The session bus answers |
| `SSD-PKG-001` | portal-frontend | `xdg-desktop-portal` is installed |
| `SSD-SERVICE-001` | portal-frontend | `xdg-desktop-portal.service` is not failed or masked (inactive is normal) |
| `SSD-PORTAL-001` | portal-frontend | The frontend runs or can start, and offers ScreenCast |
| `SSD-PORTAL-002` | portal-backend | The configured ScreenCast backend exists and the bus confirms it can answer |
| `SSD-PORTAL-003` | portal-frontend | No `portals.conf` or `.portal` file is silently ignored |
| `SSD-PORTAL-004` | portal-backend | The backend can share single windows (AvailableSourceTypes includes "window") |
| `SSD-DESKTOP-001` | portal-backend | The setup matches the desktop's defaults ([what they are](desktops.md)) |
| `SSD-COMPOSITOR-001` | compositor | The compositor service the backend captures from runs (Mutter's on GNOME) |
| `SSD-PW-001` | pipewire | PipeWire answers, or will start on demand through `pipewire.socket` |
| `SSD-WP-001` | wireplumber | WirePlumber is running and connected to PipeWire |

Every finding names its evidence, the next step (only ever printed, never run) and a command to check the result
afterwards. Codes are stable; a check that is removed keeps its code unused.
