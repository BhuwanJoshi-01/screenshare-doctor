# Apps and symptoms

`screenshare-doctor troubleshoot screenshare --app NAME --symptom SYMPTOM` starts from what you see. The symptom
decides which checks are relevant and in which order; the app adds hints about how it shares the screen. Both are
data: [`symptoms.json`](../src/screenshare_doctor/troubleshoot/symptoms.json) and
[`apps.json`](../src/screenshare_doctor/troubleshoot/apps.json). Hints explain findings; they never decide a check.

## Symptoms

| `--symptom` | What you see | Checked first |
| --- | --- | --- |
| `no-picker` | Clicking Share shows no screen or window picker | the portal side: the user manager's variables, the bus, the frontend, the ScreenCast route |
| `black-screen` | The picker works, but viewers see a black or frozen frame | the compositor, PipeWire, WirePlumber |
| `missing-window` | The window I want is not offered | the backend's source types (window sharing), the route |
| `permission-denied` | The app says screen sharing was denied or is not allowed | the frontend and its backend; the permission store is **not** read yet |
| `app-only` | Only some apps' windows can be shared | whether apps started here run natively on Wayland |

Without `--symptom` every check is shown.

## Apps

Recognised by name, alias or Flatpak id. Each hint names its source and how strong it is.

| `--app` | Hints about | Sources |
| --- | --- | --- |
| `firefox` (also LibreWolf, Floorp) | Wayland by default since 121; shares through the portal with no extra setting | [Firefox 121 release notes](https://www.mozilla.org/firefox/121.0/releasenotes/), [Red Hat KB 6712111](https://access.redhat.com/solutions/6712111) |
| `chrome`, `chromium`, `edge`, `brave`, `vivaldi` | PipeWire capture by default since 110; `--ozone-platform-hint=auto` by default since 140 | [Red Hat KB 6712111](https://access.redhat.com/solutions/6712111), [Phoronix](https://www.phoronix.com/news/Chrome-Auto-Ozone-Platform) |
| `discord`, `slack`, `signal`, `vscode`, other Electron apps | under XWayland only X11 windows were captured; Electron 38 picks Wayland automatically | [electron#36660](https://github.com/electron/electron/issues/36660), [electron#48002](https://github.com/electron/electron/pull/48002) |
| `obs` | the PipeWire capture sources and what their absence means (low confidence: a forum thread) | [OBS forum](https://obsproject.com/forum/threads/missing-screen-window-capture-even-though-pipewire-is-running.150377) |

Whether the app is installed as a **Flatpak** is read from `/var/lib/flatpak/app/<id>` and
`~/.local/share/flatpak/app/<id>` (stat only); Flatpak apps always share through the portal
([Flatpak documentation](https://docs.flatpak.org/en/latest/desktop-integration.html#portals)).

An app without a profile still gets every relevant check. To add one, open a pull request against `apps.json` with
a source for each hint; claims without a source are not accepted.
