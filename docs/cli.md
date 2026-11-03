# Command reference

Every command is read-only; see [What it promises](../README.md#what-it-promises). Exit codes: 0 the command ran
(whatever it found), 1 `--strict` failure, 2 usage or internal error, 3 required context missing, 130 Ctrl+C.

## `check session`

```bash
screenshare-doctor check session
```

Shows what kind of session the desktop is, where the tool runs relative to it, which desktop it is, and whether the
display sockets exist:

```text
screenshare-doctor 0.1.0: session

Session     Wayland (from this environment)
Running in  a terminal of the desktop
Desktop     GNOME (XDG_CURRENT_DESKTOP=ubuntu:GNOME); the portal reads ubuntu, gnome
Wayland     WAYLAND_DISPLAY=wayland-0, socket found
X11         DISPLAY=:0, socket found
logind      session 63: wayland, user, seat0, active
```

(Real output from Ubuntu 26.04 with GNOME 50.1.)

**What it reads**

- These session variables and nothing else from the environment: `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`,
  `XDG_SESSION_DESKTOP`, `DESKTOP_SESSION`, `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR`, `XDG_SESSION_ID`,
  `DBUS_SESSION_BUS_ADDRESS` (without its `guid`), and whether `SSH_CONNECTION`, `SSH_CLIENT` or `SSH_TTY` is set
  (their values name the remote machine and are never kept).
- `stat()` of `XDG_RUNTIME_DIR`, the Wayland socket and the local X11 socket (`/tmp/.X11-unix/X<n>`). Nothing is
  opened or connected to.
- logind, through `loginctl show-session <XDG_SESSION_ID>`, `loginctl show-user <uid> -p Display` and
  `loginctl show-session <Display>`. These need no privileges and change nothing.

**How it decides**

- **Session**: inside the desktop, the environment decides, because apps started from there use it. Over SSH, or
  with no display variables (a service, a container, a terminal started by the user manager), logind's view of the
  user's graphical session decides. The line says which source answered. "No graphical session" is only reported
  when logind says so; without an answer the session is unknown.
- **Running in**: an SSH login (from the SSH variables or a remote logind session), a terminal of the desktop
  (a display variable is set), a text console (`tty` session), or outside the desktop.
- **Desktop**: the first entry of `XDG_CURRENT_DESKTOP` that names a known desktop, after splitting it on `:` and
  lower-casing it as xdg-desktop-portal does. Vendor prefixes such as `ubuntu`, `pop` or `zorin` are skipped. Known
  desktops without their own checks (Budgie, Cinnamon, COSMIC…) are named as such, so `Budgie:GNOME` is not taken
  for GNOME. Only when `XDG_CURRENT_DESKTOP` names nothing known is `XDG_SESSION_DESKTOP` or `DESKTOP_SESSION`
  used. Entries the portal ignores (anything but letters, digits, `-` and `_`, such as a stray space) are listed.
- **Notes** list what does not add up: `XDG_SESSION_TYPE=wayland` without `WAYLAND_DISPLAY` (apps fall back to
  X11), a nested compositor, a socket that no longer exists, logind and the environment disagreeing.

**Exit code**: 0 when a Wayland or X11 session was found, 3 when there is none or it cannot be told.

## `check services`

```bash
screenshare-doctor check services
```

Shows, for each part of the stack, whether its package is installed and the state of its user service, then the
environment the user manager starts portals in:

```text
screenshare-doctor 0.1.0: services

Component         Package               User service
portal frontend   1.21.1+ds-1ubuntu3.1  running (static)
GNOME backend     50.0-0ubuntu1         running (static)
GTK backend       1.15.3-2ubuntu1       running (static)
KDE backend       not installed         no unit
wlr backend       not installed         no unit
Hyprland backend  not installed         no unit
PipeWire          1.6.2-1ubuntu1.2      socket: running (enabled); service: running (enabled)
WirePlumber       0.5.13-1ubuntu1.1     running (enabled)
Packages from dpkg.
Portals are started on demand: "not running" is normal until an app asks for one.

Activation environment (what portals started by the user manager see):
  XDG_CURRENT_DESKTOP  ubuntu:GNOME  (same as this shell)
  XDG_SESSION_TYPE     wayland       (same as this shell)
  WAYLAND_DISPLAY      wayland-0     (same as this shell)
  DISPLAY              :0            (same as this shell)
```

(Real output from Ubuntu 26.04 with GNOME 50.1.)

**What it reads**

- The package database, with a query command only: `dpkg-query -W`, `rpm -q` or `pacman -Q`, for
  `xdg-desktop-portal`, its gnome, gtk, kde, wlr and hyprland backends, `pipewire` and `wireplumber`. A package
  manager is used only when its program and its database both exist. Without one, the portal programs are looked
  for in `/usr/libexec`, `/usr/lib` and `/usr/local/libexec`; then "unknown" may mean "not installed".
- The user manager: `systemctl --user show` for the units of those components (Plasma 6 calls its backend
  `plasma-xdg-desktop-portal-kde.service`) and `systemctl --user show-environment`. Of the environment, only the
  session variables listed under [`check session`](#check-session) are kept; everything else is discarded unread.

Nothing is started, stopped or reloaded.

**Why the activation environment matters**: portals are D-Bus services started by the user manager, so they read
`XDG_CURRENT_DESKTOP` and `WAYLAND_DISPLAY` from its environment, not from your terminal. A compositor that does not
export its variables to the manager (`dbus-update-activation-environment --systemd …`, `systemctl --user
import-environment …`) leaves the portal unable to pick the right backend, even though everything looks right in
the shell. When the tool runs in the desktop, each value is compared with the shell's.

**Exit code**: 0, also when systemd or a package manager is missing; what could not be read is listed.

## `check dbus`

```bash
screenshare-doctor check dbus
```

Shows which portal services are on the session bus, whether the bus could start them, and what the running ones
offer for screen sharing:

```text
screenshare-doctor 0.1.0: D-Bus

Session bus reachable

Component          Running  Can start  ScreenCast
portal frontend    yes      yes        version 5; sources: monitor, window, virtual; cursor: hidden, embedded, metadata
GNOME backend      yes      yes        version 5; sources: monitor, window, virtual; cursor: hidden, embedded, metadata
GTK backend        yes      yes        not implemented
KDE backend        no       no         -
wlr backend        no       no         -
Hyprland backend   no       no         -
Mutter ScreenCast  yes      no         version 4
Only services that were already running were contacted; nothing was started.
```

(Real output from Ubuntu 26.04 with GNOME 50.1.)

**What it reads**, in this order, with `busctl --user --json=short`:

1. The bus daemon (`org.freedesktop.DBus`), which never starts a service to answer: `ListActivatableNames` once (of
   the list, only the names below are kept), then `NameHasOwner` for `org.freedesktop.portal.Desktop`, the gnome,
   gtk, kde, wlr and hyprland backends (`org.freedesktop.impl.portal.desktop.*`) and `org.gnome.Mutter.ScreenCast`.
2. Only for names that are running, and always with `--auto-start=no`: `Introspect` on
   `/org/freedesktop/portal/desktop`, and, where the ScreenCast interface exists, its `version`,
   `AvailableSourceTypes` and `AvailableCursorModes`. For GNOME, the `Version` of Mutter's ScreenCast service.

A service that is not running is reported as such; `--auto-start=no` means even one that stopped between the two
steps fails instead of being started.

**Reading the result**

- *Running / Can start*: portals normally start on demand, so "no / yes" is fine. "no / no" for your desktop's
  backend means nothing can start it: the backend is not installed or its D-Bus service file is missing.
- *ScreenCast*: the frontend only offers ScreenCast when a backend implements it. Sources are the specification's
  monitor, window and virtual; a backend without "window" cannot share single windows. "not implemented" is a
  fact from introspection; "unknown" means it could not be read (see the list below the table).

**Exit code**: 0 when the session bus answered, 3 when it could not be reached.

## `routes explain`

```bash
screenshare-doctor routes explain              # ScreenCast
screenshare-doctor routes explain Screenshot   # or org.freedesktop.portal.Screenshot
```

Predicts which backend xdg-desktop-portal uses for an interface, says which entry in which file decided it, and
checks the prediction on the session bus:

```text
screenshare-doctor 0.1.0: route for ScreenCast

Interface   ScreenCast (org.freedesktop.portal.ScreenCast)
Predicted   gnome (org.freedesktop.impl.portal.desktop.gnome)
Decided by  default=gnome;gtk in /usr/share/xdg-desktop-portal/gnome-portals.conf
Portal      xdg-desktop-portal 1.21.1+ds-1ubuntu3.1 (selection rules of 1.21.1 and later; read as 1.21.1)
Desktops    ubuntu, gnome (XDG_CURRENT_DESKTOP of the user manager)
On D-Bus    gnome is running and implements it; the frontend offers it

How it was decided:
  1. /usr/share/xdg-desktop-portal/gnome-portals.conf: gnome is listed and implements org.freedesktop.impl.portal.ScreenCast

Configuration search order (highest priority first):
   1. ~/.config/xdg-desktop-portal: nothing
   2. /etc/xdg/xdg-ubuntu/xdg-desktop-portal: nothing
   …
  11. /usr/share/xdg-desktop-portal: gnome-portals.conf
  12. /var/lib/snapd/desktop/xdg-desktop-portal: nothing
  13. /usr/share/xdg-desktop-portal: gnome-portals.conf
```

(Real output from Ubuntu 26.04 with GNOME 50.1, shortened.)

**What it reads**: everything `check services` and `check dbus` read, plus the candidate `portals.conf` files and
the `*.portal` descriptors in the frontend's search directories, read-only and at most 64 KiB each. The desktop
names and directories are the user manager's; without systemd the shell's are used and the output says so.

**How it decides**: with the rules of the installed xdg-desktop-portal version, which changed several times; see
[How a portal request finds its backend](portal-routing.md). If the version is unknown, the newest rules are used
and the output says the prediction may be wrong. Files the portal would ignore (unreadable, no `[preferred]`
group, an invalid value) are listed with the reason.

**Exit code**: 0, whatever the prediction; 2 when the argument is not a portal interface name.
