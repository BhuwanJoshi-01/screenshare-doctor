# Session environment fixtures

Each `*.env` file holds the session variables of one desktop as `NAME=value` lines; `#` starts a comment.
Values that identify a machine (the D-Bus `guid`) are replaced.

| File | Source |
| --- | --- |
| `gnome-wayland-ubuntu.env` | **Real**: Ubuntu 26.04, GNOME 50.1 on Wayland, captured 2026-11-03 from a terminal in the session |
| `kde-plasma-wayland.env` | Synthetic: the values Plasma 6 sets on Wayland, not captured yet |
| `hyprland.env` | Synthetic: the values Hyprland sets when started from a display manager, not captured yet |
| `gnome-x11.env` | Synthetic: a GNOME on Xorg session |
| `ssh-shell.env` | Synthetic: a login over SSH without X forwarding |
| `linux-console.env` | Synthetic: a text console login (`Ctrl+Alt+F3`) |

Replace a synthetic file with a real capture when you have one (see CONTRIBUTING.md), and update this table.
