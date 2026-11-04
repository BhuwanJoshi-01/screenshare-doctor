# Support matrix

Only what was actually run is listed as tested. Everything else may work, but is not claimed. Test reports from other
desktops are very welcome (open a *Test report* issue, and attach `screenshare-doctor report`).

## Tested on a real session

| Distribution | Desktop | Stack | Result |
| --- | --- | --- | --- |
| Ubuntu 26.04 LTS, kernel 7.0 | GNOME 50.1, Wayland (GDM) | xdg-desktop-portal 1.21.1, -gnome 50.0, -gtk 1.15.3, PipeWire 1.6.2, WirePlumber 0.5.13, systemd 259 | every check passes; the opt-in integration tests confirm that no service is started and that the report carries no user name |

| Fedora 45 (VM) | KDE Plasma 6.8.2, Wayland (SDDM) | xdg-desktop-portal 1.22.1, -kde 6.8.2, -gtk 1.15.3, PipeWire 1.6.11, WirePlumber 0.5.19, rpm 6.1.0 | every check passes once `pipewire-utils` (which has `pw-dump`) is installed; without it SSD-PW-001 is unknown |
| Arch Linux (VM) | Hyprland 0.57.1, Wayland (autologin on tty1) | xdg-desktop-portal 1.22.1, -hyprland 1.5.0, -gtk 1.15.3, PipeWire 1.6.10, WirePlumber 0.5.18, pacman 7.1.0 | every check passes; while the portal and PipeWire wait to be started on demand, SSD-PORTAL-004 is not tested |

GNOME was run from a VS Code terminal (no `XDG_SESSION_ID`), from a GNOME terminal, and with an empty environment
(`env -i`), where the session is found through logind and the missing desktop variables are reported.

KDE Plasma and Hyprland ran in QEMU virtual machines with a virtio GPU, inside the real desktop session: from
Plasma's autostart and as a child of the compositor (`hyprctl dispatch`), so the tool saw the session's own
environment. On both, the well-known names on the session bus and the user units were the same before and after
every command. On KDE a `~/.config/xdg-desktop-portal/portals.conf` that sets `ScreenCast=none` failed
SSD-PORTAL-002 and named the file. Sample reports from both sessions are in [sample-reports](sample-reports/).

## Tested in CI (no desktop session)

| Platform | What runs |
| --- | --- |
| Ubuntu, Python 3.11–3.14 | the full test suite on real captures from the machine above and labelled synthetic fixtures |
| Ubuntu, Python 3.12 | the built wheel installed into an empty environment and run without a desktop session |

## Not validated yet

- **KDE Plasma and Hyprland on real hardware**: validated in virtual machines only, without a GPU driver of their
  own; reports from real machines are especially welcome.
- **wlroots compositors** (sway, river, Wayfire, labwc): defaults from upstream sources only.
- **openSUSE and other distributions**: `rpm` and `pacman` were run on Fedora 45 and Arch; other package managers
  are not supported, and the tool falls back to looking for the portal files.
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
