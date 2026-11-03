# Privacy and side effects

Reports from this tool are meant to be pasted into public bug trackers, so it is built to collect little, change
nothing and hide what identifies you.

## What it reads

| Source | What is kept |
| --- | --- |
| Environment variables | only `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`, `XDG_SESSION_DESKTOP`, `DESKTOP_SESSION`, `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR`, `XDG_SESSION_ID`, `DBUS_SESSION_BUS_ADDRESS` (without its `guid`), whether an SSH variable is set (not its value), and for portal files `HOME`, `XDG_CONFIG_HOME`, `XDG_CONFIG_DIRS`, `XDG_DATA_HOME`, `XDG_DATA_DIRS`, `XDG_DESKTOP_PORTAL_DIR`. Variables are looked up by name; the environment is never listed |
| `stat()` | the runtime directory, the Wayland and X11 sockets, two Flatpak installation directories for the app you name |
| `loginctl show-user`, `show-session` | session id, type, class, seat, remote, active, state. Not your user name |
| Package database (`dpkg-query -W`, `rpm -q`, `pacman -Q`) | installed state and version of eight named packages |
| `systemctl --user show`, `show-environment` | the state of nine named units; of the user manager's environment, the same variables as above |
| Session bus (`busctl`) | whether seven portal names run or can start (of the list of activatable names, only those seven are kept), and the interfaces and ScreenCast properties of the ones that run |
| Portal files | `portals.conf` candidates and `*.portal` descriptors in the portal's search directories, at most 64 KiB each, reduced to backend and interface names |
| `pw-dump` | PipeWire's version, whether WirePlumber, the portal and the compositor are connected, a **count** of other clients, counts of video nodes. Application names, media titles and device names are discarded while parsing |

## What it never does

- Open a screen-sharing request or picker, read the screen, or record anything.
- Start, stop, restart or reload a service. A portal that is not running is reported, not started: services are
  only contacted when already running, and always with `busctl --auto-start=no`. PipeWire is only asked when
  `pipewire.service` already runs, because connecting to its socket would start it.
- Change any setting or file, or need `sudo`. The only file it writes is the one you name with
  `report --output`, which it will not overwrite without `--force`.
- Connect to the network. The test suite blocks network access to make sure.

A test runs every command and checks each program it would start against a read-only allowlist
(`tests/contract/test_passive_harness.py`); an opt-in test checks on a real session that no bus name or user unit
appears during a run.

## What is redacted

Before anything is printed or written, in every format: your home directory (shown as `~`), other home directories
(`/home/<user>`), your user name and host name, values of secret-looking assignments (`password=…`, `token: …`),
credentials in URLs and known token formats. Each report says what was redacted. A test plants secrets in the
environment, the user manager, a portal file and a probe error and checks that none reaches any output.

Session ids, seat names, package versions and portal file paths outside your home are kept: they are what a
maintainer needs to reproduce the problem.
