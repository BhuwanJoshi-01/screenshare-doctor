# Troubleshooting

The common causes of broken screen sharing on Wayland, the check that finds each one, and what to do. Start with

```bash
screenshare-doctor troubleshoot screenshare --app YOUR-APP --symptom no-picker   # or black-screen, missing-window…
```

and come back here for the code it names.

## No picker appears

| Check | Cause | Fix |
| --- | --- | --- |
| `SSD-SESSION-004` | The user manager does not know `WAYLAND_DISPLAY` or `XDG_CURRENT_DESKTOP`, typical when a compositor is started from a TTY (Hyprland, sway). The portal starts but its backend cannot reach the compositor. | Add `dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP` to your compositor's startup, then log in again. |
| `SSD-SESSION-003` | The portal's `XDG_CURRENT_DESKTOP` is unset or contains an entry it drops (a space). | Set it from the session startup; use only letters, digits, `-` and `_`. |
| `SSD-PORTAL-002` | No installed backend implements ScreenCast, a `portals.conf` disables it with `none`, or the chosen backend cannot start. | `screenshare-doctor routes explain ScreenCast` shows the file and line; install the backend or fix the file. |
| `SSD-PORTAL-003` | A `portals.conf` you wrote is ignored because the portal cannot read it. | Fix the reported line, or remove the file. |
| `SSD-DESKTOP-001` | Your desktop's backend or its `portals.conf` is missing. | Install the package named in the finding ([desktop defaults](desktops.md)). |
| `SSD-SERVICE-001` | `xdg-desktop-portal.service` is masked or failed. | `journalctl --user -u xdg-desktop-portal -b` says why; unmask it if masked. |

## The picker works, the stream is black or frozen

| Check | Cause | Fix |
| --- | --- | --- |
| `SSD-COMPOSITOR-001` | On GNOME, Mutter's screen-cast service is not running. | Log out and in; check gnome-shell's log. |
| `SSD-PW-001` | PipeWire is not running and cannot start, or has failed. | `systemctl --user enable --now pipewire.socket pipewire.service` |
| `SSD-WP-001` | WirePlumber is not connected, so the stream is never linked to the app. | `systemctl --user enable --now wireplumber.service` |
| `SSD-SESSION-002` | The app was started from a shell without `WAYLAND_DISPLAY` and runs through XWayland. | Start it from the desktop's launcher, or run it natively (see the app's hints). |

## The window I want is missing

| Check | Cause | Fix |
| --- | --- | --- |
| `SSD-PORTAL-004` | The backend offers whole screens only. | Share the screen, or use a backend with window support for your desktop. |
| `SSD-SESSION-002` | The app runs through XWayland and lists X11 windows only. | Run it natively on Wayland. |

## Still stuck

`screenshare-doctor report --output report.md` writes a redacted report. Read it, then attach it to an issue in the
app's tracker or here; it shows the maintainers the whole chain at once.
