# How a portal request finds its backend

An app that wants to share the screen calls `org.freedesktop.portal.ScreenCast` on the **portal frontend**
(`xdg-desktop-portal`, bus name `org.freedesktop.portal.Desktop`). The frontend passes the request to a
**backend** that implements `org.freedesktop.impl.portal.ScreenCast`: `xdg-desktop-portal-gnome`, `-kde`, `-wlr`,
`-hyprland`… Which backend it picks is decided once, when the frontend starts, from three inputs:

1. **Its own `XDG_CURRENT_DESKTOP`**, split on `:` and lower-cased. Entries that are not made of letters, digits,
   `-` and `_` are dropped. This is the user manager's environment, not your terminal's (see
   [`check services`](cli.md#check-services)).
2. **`portals.conf` files**, searched in this order (`DESKTOP-portals.conf` for each desktop name first, then
   `portals.conf`, in each directory):
   1. `$XDG_CONFIG_HOME/xdg-desktop-portal` (default `~/.config/xdg-desktop-portal`)
   2. each `$XDG_CONFIG_DIRS` entry + `/xdg-desktop-portal` (default `/etc/xdg`)
   3. `/etc/xdg-desktop-portal`
   4. `$XDG_DATA_HOME/xdg-desktop-portal` (default `~/.local/share/xdg-desktop-portal`)
   5. each `$XDG_DATA_DIRS` entry + `/xdg-desktop-portal` (default `/usr/local/share:/usr/share`)
   6. `/usr/share/xdg-desktop-portal`

   `XDG_DESKTOP_PORTAL_DIR` replaces all of them.
3. **`.portal` descriptors** in the data directories' `xdg-desktop-portal/portals/`: each names a backend's bus name,
   the interfaces it implements and, in the deprecated `UseIn` key, the desktops it is meant for. The first file of a
   name wins.

A `portals.conf` has one group:

```ini
[preferred]
default=gnome;gtk;
org.freedesktop.impl.portal.Secret=gnome-keyring;
```

An interface entry is tried before `default`. In a list, backends are tried in order and skipped when they are not
installed or do not implement the interface; `*` means "the first installed backend that implements it" (preferring
those whose `UseIn` matches the desktop); `none` disables the interface. When no configuration decides, the
frontend falls back to `UseIn`, then to `xdg-desktop-portal-gtk`, and otherwise offers no backend for the interface.

## The rules depend on the version

The selection changed between releases, in ways that decide real cases. `routes explain` applies the rules of the
installed version, read from each release's source code:

| Release | What differs |
| --- | --- |
| before 1.17 | No `portals.conf` at all: `UseIn`, then gtk. |
| 1.17, 1.18 | Only the first configuration file found is used. Its lists are **not** read in order: the first installed backend (sorted by `UseIn` match, then name) that the list names wins. An interface entry replaces `default` completely. |
| 1.19 to 1.21.0 | Lists are read in order, and an interface entry that finds nothing falls back to `default`. Still only the first file. `default=*` matches nothing, because the lookup used the key name `default` as the interface name. |
| 1.20.1 and later | Descriptors are also read from the user and `$XDG_DATA_DIRS` data directories, not only `/usr/share`. |
| 1.21.1 and later | Every directory's configuration is consulted in order until one names a usable backend; `default=*` works. |

Sources: `src/portal-impl.c` (1.18.4, 1.19.0), `src/xdp-portal-impl.c` (1.20.x), `src/xdp-portal-config.c` (1.21.0)
and `desktop-portal/xdp-portal-config.c` (1.21.1 and main) in
[flatpak/xdg-desktop-portal](https://github.com/flatpak/xdg-desktop-portal), read 2026-11-03.

One consequence: before 1.21.1, a `~/.config/xdg-desktop-portal/portals.conf` that names a backend you do not have
hides the system's working configuration entirely, and the deprecated `UseIn` key decides instead. From 1.21.1 the
frontend moves on to the next file.

## Configured is not the same as working

The prediction says what the configuration selects. `routes explain` then checks it against the session bus: is the
backend running or at least activatable, does it really export the interface, and does the frontend offer the
public interface? A backend that is "not running but can start" is normal: portals start on demand.
