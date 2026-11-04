# What each desktop ships for screen sharing

`check desktop` compares your setup with these defaults. They are **expectations, not verdicts**: a different
backend or your own `portals.conf` can be a deliberate, working choice, so a difference is a warning. The data is in
[`src/screenshare_doctor/bundles/desktops.json`](../src/screenshare_doctor/bundles/desktops.json); each entry names
the upstream file it was read from (all read on 2026-11-03). Corrections are welcome, with a link.

| | GNOME | KDE Plasma | Hyprland | wlroots (sway, river, Wayfire, labwc) |
| --- | --- | --- | --- | --- |
| ScreenCast backend | `gnome` | `kde` | `hyprland` | `wlr` |
| Package | `xdg-desktop-portal-gnome` | `xdg-desktop-portal-kde` | `xdg-desktop-portal-hyprland` | `xdg-desktop-portal-wlr` |
| User unit | `xdg-desktop-portal-gnome.service` | `plasma-xdg-desktop-portal-kde.service` | `xdg-desktop-portal-hyprland.service` | `xdg-desktop-portal-wlr.service` |
| Desktop's `portals.conf` | `gnome-portals.conf`: `default=gnome;gtk;` | `kde-portals.conf`: `default=kde` | `hyprland-portals.conf`: `default=hyprland;gtk` | none installed (a sample is in the source tree) |
| Installed by | gnome-session | plasma-workspace | Hyprland | — |
| Compositor service the backend needs | `org.gnome.Mutter.ScreenCast` on the session bus | (Wayland protocol, not checked) | (Wayland protocol, not checked) | (Wayland protocol, not checked) |

Note the "installed by" row: the desktop's `portals.conf` does **not** come with the portal backend. If
`gnome-portals.conf` is missing, look at gnome-session, not at xdg-desktop-portal-gnome. Without the file the portal
falls back to the deprecated `UseIn` key of the `.portal` files, then to gtk (see
[portal routing](portal-routing.md)).

## Sources

- GNOME: [gnome-session `data/gnome-portals.conf`](https://gitlab.gnome.org/GNOME/gnome-session/-/blob/main/data/gnome-portals.conf),
  [xdg-desktop-portal-gnome `data/`](https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome/-/tree/main/data),
  [`src/gnomescreencast.c`](https://gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome/-/blob/main/src/gnomescreencast.c)
  (talks to `org.gnome.Mutter.ScreenCast`).
- KDE Plasma: [plasma-workspace `portal-configuration/kde-portals.conf`](https://invent.kde.org/plasma/plasma-workspace/-/blob/master/portal-configuration/kde-portals.conf),
  [xdg-desktop-portal-kde `data/`](https://invent.kde.org/plasma/xdg-desktop-portal-kde/-/tree/master/data) (`kde.portal`,
  `plasma-xdg-desktop-portal-kde.service`).
- Hyprland: [Hyprland `assets/hyprland-portals.conf`](https://github.com/hyprwm/Hyprland/blob/main/assets/hyprland-portals.conf),
  [xdg-desktop-portal-hyprland](https://github.com/hyprwm/xdg-desktop-portal-hyprland) (`hyprland.portal`,
  `contrib/systemd/xdg-desktop-portal-hyprland.service.in`).
- wlroots: [xdg-desktop-portal-wlr](https://github.com/emersion/xdg-desktop-portal-wlr) (`wlr.portal`,
  `contrib/wlroots-portals.conf`, `contrib/systemd/`).

## What is checked

1. The backend package is installed (from the package manager).
2. Its `.portal` file exists, is valid and declares `org.freedesktop.impl.portal.ScreenCast`.
3. The desktop's `portals.conf` is installed and the portal can read it.
4. ScreenCast is routed to the desktop's backend, with the rules of your portal version.
5. The backend is running or can be started on the session bus.
6. The compositor service the backend needs is running (GNOME only).

GNOME, KDE Plasma and Hyprland are tested on real sessions ([support matrix](support-matrix.md)); wlroots
compositors are not yet.
