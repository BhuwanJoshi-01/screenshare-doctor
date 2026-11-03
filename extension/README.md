# Screenshare Doctor for GNOME Shell

A top-bar indicator for GNOME 46 to 50. Open its menu and it runs the `screenshare-doctor` command-line tool, then
shows whether screen sharing can work on this desktop and, if not, which check failed and what to do next. The icon
keeps the worst result until the next check: a shared screen when all is well, a warning, an error, or a question
mark when the check could not run.

The extension does no checking itself and runs nothing while its menu is closed. Everything it shows comes from
`screenshare-doctor doctor --format json`, which is passive: no screen-sharing request, nothing started or changed.

## Install

1. Install the tool: `uv tool install screenshare-doctor` (or `pipx install screenshare-doctor`).
2. Install the extension from [extensions.gnome.org](https://extensions.gnome.org) (once it is published there), or
   from a release zip:

   ```bash
   gnome-extensions install --force screenshare-doctor@bhuwanjoshi-01.github.io.shell-extension.zip
   ```

   then log out and in (Wayland) and enable it in the Extensions app.

If the tool lives outside `PATH` and `~/.local/bin`, set its path in the extension's preferences.

## Menu

- **Check again** runs the tool once more.
- **Copy a report for a bug tracker** copies `screenshare-doctor report` (Markdown, redacted by the tool) to the
  clipboard. Read it before you share it.
- **Open the troubleshooting guide** opens the project's guide in your browser.

Without the tool, the menu offers to copy the install command or open the project page.

## How it is built

| File | Role |
| --- | --- |
| `extension.js` | `enable()` adds the indicator, `disable()` destroys it |
| `indicator.js` | the menu; runs the tool on open only |
| `cli.js` | runs the tool with `Gio.Subprocess`, asynchronously; cancelling kills it and removes the 60 s kill timeout |
| `report.js` | turns the JSON report into what the menu shows; no GNOME imports |
| `prefs.js` | the preferences page (path of the tool) |
| `schemas/` | the `cli-path` setting |

## Development

```bash
scripts/pack-extension.sh                  # dist/<uuid>.shell-extension.zip
(cd extension && node --test)              # report.js
gjs -m extension/tests/cli.gjs.js          # cli.js, against stand-in programs
scripts/test-extension-nested.sh           # headless nested GNOME Shell: enable, preferences, disable
```

The extension is GPL-2.0-or-later ([LICENSE](LICENSE)); the command-line tool is MIT.
