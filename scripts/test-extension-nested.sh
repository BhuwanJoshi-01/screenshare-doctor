#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Load the packed extension into a headless, nested GNOME Shell and check that it
# enables and disables without errors. Everything happens on a private D-Bus with
# temporary data and config directories; the running desktop is not touched. The
# preferences window is opened on the nested display too.
# Needs gnome-shell (46 or newer), dbus-run-session and glib-compile-schemas.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UUID="screenshare-doctor@bhuwanjoshi-01.github.io"
ZIP="$("$REPO_DIR/scripts/pack-extension.sh")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/data/gnome-shell/extensions/$UUID" "$WORK/config"
unzip -q "$ZIP" -d "$WORK/data/gnome-shell/extensions/$UUID"
glib-compile-schemas "$WORK/data/gnome-shell/extensions/$UUID/schemas"

# Stand-ins for the command-line tool: one that answers with the sample report, one
# that never answers (to prove that disabling the extension kills a running check).
printf '#!/bin/sh\ncat %q\n' "$REPO_DIR/extension/tests/healthy.json" > "$WORK/ssd-answers"
printf '#!/bin/sh\nexec sleep 299.5\n' > "$WORK/ssd-hangs"
chmod +x "$WORK/ssd-answers" "$WORK/ssd-hangs"

# A test-only extension that drives the real menu; it is never packaged.
DRIVER="ssd-test-driver@localhost"
mkdir -p "$WORK/data/gnome-shell/extensions/$DRIVER"
cat > "$WORK/data/gnome-shell/extensions/$DRIVER/metadata.json" <<META
{"uuid": "$DRIVER", "name": "test driver", "description": "test only", "shell-version": ["46", "47", "48", "49", "50"]}
META
cat > "$WORK/data/gnome-shell/extensions/$DRIVER/extension.js" <<DRIVE
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const after = (ms, step) => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    step();
    return GLib.SOURCE_REMOVE;
});

export default class Driver extends Extension {
    enable() {
        const indicator = Main.panel.statusArea['$UUID'];
        indicator._settings.set_string('cli-path', '$WORK/ssd-answers');
        indicator.menu.open();
        after(3000, () => {
            console.log('ssd-test: headline: ' + indicator._header.label.text);
            indicator.menu.close();
            indicator._settings.set_string('cli-path', '$WORK/ssd-hangs');
            indicator.menu.open();
        });
        after(4000, () => {
            console.log('ssd-test: hanging check started: ' + indicator._header.label.text);
            indicator.menu.close();
        });
    }

    disable() {
    }
}
DRIVE

cat > "$WORK/run.sh" <<INNER
#!/usr/bin/env bash
set -u
info() {
  gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Extensions.GetExtensionInfo "$UUID" | grep -o "'state': <[0-9.]*>\|'error': <'[^']*'>"
}
gsettings set org.gnome.shell disable-user-extensions false
gnome-shell --headless --wayland --no-x11 --virtual-monitor 1280x800 \
  --wayland-display "ssd-test-\$\$" > "$WORK/shell.log" 2>&1 &
pid=\$!
for _ in \$(seq 1 30); do
  gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell \
    --method org.freedesktop.DBus.Peer.Ping > /dev/null 2>&1 && break
  sleep 1
done
sleep 3
gnome-extensions enable "$UUID"; sleep 3
echo "enabled:  \$(info | tr '\n' ' ')"
WAYLAND_DISPLAY="ssd-test-\$\$" gnome-extensions prefs "$UUID" && echo "prefs:    opened"
sleep 2
gnome-extensions enable "$DRIVER"; sleep 6
pgrep -f "sleep 299.5" > /dev/null && echo "hanging:  running"
gnome-extensions disable "$UUID"; sleep 2
echo "disabled: \$(info | tr '\n' ' ')"
pgrep -f "sleep 299.5" > /dev/null || echo "hanging:  killed"
kill "\$pid"; wait "\$pid" 2> /dev/null
INNER
chmod +x "$WORK/run.sh"

out="$(XDG_DATA_HOME="$WORK/data" XDG_CONFIG_HOME="$WORK/config" dbus-run-session -- "$WORK/run.sh" 2> "$WORK/bus.log")"
echo "$out"
errors="$(cat "$WORK/shell.log" "$WORK/bus.log" | grep -c "JS ERROR" || true)"
echo "JS errors in the shell and preferences logs: $errors"
[[ "$out" == *"enabled:  'state': <1.0> 'error': <''>"* ]] || { echo "the extension did not become active"; exit 1; }
[[ "$out" == *"disabled: 'state': <2.0> 'error': <''>"* ]] || { echo "the extension did not disable cleanly"; exit 1; }
[[ "$out" == *"prefs:    opened"* ]] || { echo "the preferences did not open"; exit 1; }
grep -o "ssd-test: .*" "$WORK/shell.log" || echo "nothing logged by the test driver"
headline="$(grep -o "ssd-test: headline: .*" "$WORK/shell.log" || true)"
[[ "$headline" == *"Screen sharing should work"* ]] || { echo "the menu did not show the report"; exit 1; }
[[ "$out" == *"hanging:  running"* && "$out" == *"hanging:  killed"* ]] || {
  echo "disabling the extension did not kill the running check"; exit 1; }
[[ "$errors" == 0 ]] || { grep -h -A5 "JS ERROR" "$WORK/shell.log" "$WORK/bus.log"; exit 1; }
echo "ok"
