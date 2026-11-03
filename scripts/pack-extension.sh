#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Build the GNOME Shell extension zip for extensions.gnome.org and GitHub releases.
# Output: dist/<uuid>.shell-extension.zip
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UUID="screenshare-doctor@bhuwanjoshi-01.github.io"
SRC="$REPO_DIR/extension/$UUID"
OUT="$REPO_DIR/dist"

mkdir -p "$OUT"
rm -f "$OUT/$UUID.shell-extension.zip"
( cd "$SRC" && zip -q -r -X "$OUT/$UUID.shell-extension.zip" metadata.json ./*.js stylesheet.css schemas/*.gschema.xml )
# The extension is GPL-2.0-or-later (the command-line tool is MIT); ship its licence in the zip.
cp "$REPO_DIR/extension/LICENSE" "$OUT/LICENSE" && ( cd "$OUT" && zip -q "$UUID.shell-extension.zip" LICENSE && rm LICENSE )
echo "$OUT/$UUID.shell-extension.zip"
