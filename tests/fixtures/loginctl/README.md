# loginctl fixtures

Output of `LC_ALL=C loginctl --no-pager show-session <id> -p Id -p Type -p Class -p Remote -p Desktop -p State -p
Active -p Seat` and `loginctl --no-pager show-user <uid> -p Display`. loginctl prints the properties in its own
order, not the order they were asked for.

| File | Source |
| --- | --- |
| `show-user-display-gnome.txt` | **Real**: Ubuntu 26.04, systemd 259, the user's display session is the GNOME one |
| `show-session-gnome-wayland.txt` | **Real**: the GDM-started GNOME 50.1 Wayland session (`Desktop` is empty under GDM here) |
| `show-session-user-manager.txt` | **Real**: the `systemd --user` manager's own session (class `manager`, no seat) |
| `show-session-kde-wayland.txt` | Synthetic: a Plasma Wayland session started by SDDM |
| `show-session-ssh.txt` | Synthetic: an SSH login |
| `show-user-no-display.txt` | Synthetic: a user logged in without a graphical session |
