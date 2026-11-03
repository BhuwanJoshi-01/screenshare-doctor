# Roadmap

Requirement IDs (`WLD-001` …) are used in issues, pull requests and commit trailers (`Refs: WLD-005`). The `WLD`
prefix comes from the project's working name, Wayland Doctor; findings shown to users use `SSD-` codes instead.
A requirement is done when its tests pass and the behaviour was checked on a real desktop, not when the code is
written.

## v0.1: passive diagnosis

| ID | Feature | Done when |
| --- | --- | --- |
| WLD-001 | Session detection | Wayland, X11, SSH and no-session are told apart, and the desktop values are read without guessing |
| WLD-002 | Dependency visibility | Installed `xdg-desktop-portal*`, `pipewire`, `wireplumber` and portal backends are found where possible |
| WLD-003 | User service state | `systemctl --user` is queried read-only; systems without systemd report unknown |
| WLD-004 | D-Bus probes | The ScreenCast interface and its properties are read; absent, failed and timed out are distinct; a portal that is not running is **not** started |
| WLD-005 | Portal route analysis | `portals.conf` files are resolved with the documented precedence, and the output says why a backend was selected |
| WLD-006 | App-centred symptoms | `troubleshoot screenshare --app … --symptom …` picks the relevant checks and explains them |
| WLD-007 | Desktop rule bundles | GNOME, KDE and Hyprland expectations are documented and checked against what is really there |
| WLD-008 | Read-only reports | Terminal, JSON and Markdown; redacted by default; known unknowns are listed |
| WLD-009 | Test harness | Every default command works without a portal prompt and without root |
| WLD-010 | Real sessions | Smoke-tested on GNOME, KDE and Hyprland; untested setups are listed as such |

A small GNOME Shell extension (a top-bar indicator that runs the CLI) follows in v0.1.x, once the JSON output is
stable.

## v0.2

`test screencast --interactive`: after you confirm, a real ScreenCast request with the desktop's picker, a check
that a PipeWire stream can be opened, and a clean close of the session. Nothing is recorded or saved.

## Later

- Window picker and Flatpak-specific diagnostics; per-app launch analysis with verified process attribution.
- A larger GUI, repair plans with configuration backups, comparison of diagnostic snapshots over time.

## Not planned

Compositor patches, silent screenshots or recordings, root commands, automatic service restarts and edits to
global portal settings.
