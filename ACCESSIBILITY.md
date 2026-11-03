# Accessibility

The command-line tool prints plain text: statuses are words (PASS, WARN, FAIL, UNKNOWN), not only colours, and
`--format json` and `report` give the same content in machine-readable and Markdown form. Colours follow the
terminal's theme and disappear when output is not a terminal or `NO_COLOR` is set.

The GNOME Shell extension uses GNOME Shell's own menu widgets, so it works with the keyboard (Ctrl+Alt+Tab reaches the
top bar, then arrow keys and Enter) and with the Orca screen reader like the system menus. Each problem is a text line that starts with its status
word; the coloured icon in the top bar repeats the worst status and is never the only place it appears. Text wraps
instead of being cut off.

Not yet tested with Orca on a real session. If something is hard to use with assistive technology, please open an
issue: it is treated as a bug.
