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
