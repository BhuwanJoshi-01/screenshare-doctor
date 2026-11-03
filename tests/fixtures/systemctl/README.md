# systemctl --user fixtures

| File | Source |
| --- | --- |
| `show-units-ubuntu-gnome.txt` | **Real**: `LC_ALL=C systemctl --user --no-pager show -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState <UNITS>` on Ubuntu 26.04 (systemd 259) in a GNOME 50.1 session. The KDE, wlr and Hyprland backends are `not-found` |
| `show-environment-ubuntu-gnome.txt` | **Real variable names** from `systemctl --user show-environment` on the same machine. The allowlisted session variables and `XDG_DATA_DIRS`/`XDG_CONFIG_DIRS` keep their real values (bus `guid` removed, the home directory renamed `/home/user`); every other value is replaced with `<placeholder>` |
