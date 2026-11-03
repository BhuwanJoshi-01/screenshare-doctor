# busctl fixtures

Output of `LC_ALL=C busctl --user --no-pager --json=short …`.

| File | Source |
| --- | --- |
| `name-has-owner-true.json`, `name-has-owner-false.json` | **Real**: `call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus NameHasOwner s <name>` on Ubuntu 26.04 (systemd 259), for the GNOME backend and the absent KDE backend |
| `list-activatable-ubuntu-gnome.json` | **Real, trimmed**: `ListActivatableNames` on the same machine, keeping the `org.freedesktop.*` names and a few GNOME infrastructure ones; installed apps were removed |
