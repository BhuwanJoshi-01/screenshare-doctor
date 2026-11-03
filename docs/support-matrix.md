# Support matrix

Only what was actually run is listed as tested. Everything else may work, but is not claimed. Test reports from other
desktops are very welcome (open a *Test report* issue, and attach `screenshare-doctor report`).

## Tested on a real session

| Distribution | Desktop | Stack | Result |
| --- | --- | --- | --- |
| Ubuntu 26.04 LTS, kernel 7.0 | GNOME 50.1, Wayland (GDM) | xdg-desktop-portal 1.21.1, -gnome 50.0, -gtk 1.15.3, PipeWire 1.6.2, WirePlumber 0.5.13, systemd 259 | every check passes; the opt-in integration tests confirm that no service is started and that the report carries no user name |

Run from a VS Code terminal (no `XDG_SESSION_ID`), from a GNOME terminal, and with an empty environment
(`env -i`), where the session is found through logind and the missing desktop variables are reported.

## Tested in CI (no desktop session)

| Platform | What runs |
| --- | --- |
| Ubuntu, Python 3.11–3.14 | the full test suite on real captures from the machine above and labelled synthetic fixtures |
| Ubuntu, Python 3.12 | the built wheel installed into an empty environment and run without a desktop session |

## Not validated yet

- **KDE Plasma 6** and **Hyprland**: the desktop defaults come from their upstream sources
  ([desktops](desktops.md)) and the fixtures are synthetic; real sessions are planned in a virtual machine.
- **wlroots compositors** (sway, river, Wayfire, labwc): defaults from upstream sources only.
- **Fedora, Arch, openSUSE**: the `rpm` and `pacman` parsers are tested on synthetic output in the documented formats.
- **Without systemd** (elogind, runit, OpenRC): logind and the user services are reported as unknown by design; not
  run on such a system.
- **xdg-desktop-portal before 1.21.1**: the older selection rules ([portal routing](portal-routing.md)) were read from
  each release's source and are covered by tests, not run against those releases.
- **Flatpak apps**: detected from the installation directories; their portal permissions are not read.

## Requirements

- Linux with a graphical session to diagnose (the tool also runs elsewhere and says what it cannot see).
- Python 3.11 or newer for the tool itself.
- Optional, each only for its checks: `loginctl`, `busctl` and `systemctl` (systemd), `pw-dump` (PipeWire), and the
  distribution's package query tool.
