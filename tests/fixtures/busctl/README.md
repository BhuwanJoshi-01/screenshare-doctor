# busctl fixtures

Output of `LC_ALL=C busctl --user --no-pager --json=short …`.

| File | Source |
| --- | --- |
| `name-has-owner-true.json`, `name-has-owner-false.json` | **Real**: `call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus NameHasOwner s <name>` on Ubuntu 26.04 (systemd 259), for the GNOME backend and the absent KDE backend |
| `list-activatable-ubuntu-gnome.json` | **Real, trimmed**: `ListActivatableNames` on the same machine, keeping the `org.freedesktop.*` names and a few GNOME infrastructure ones; installed apps were removed |
| `introspect-frontend-ubuntu-gnome.json`, `introspect-gnome-backend.json`, `introspect-gtk-backend.json` | **Real**: `--auto-start=no call <name> /org/freedesktop/portal/desktop org.freedesktop.DBus.Introspectable Introspect` for xdg-desktop-portal 1.21.1 and the gnome (50.0) and gtk (1.15.3) backends. The gtk backend has no ScreenCast |
| `screencast-props-frontend.json`, `screencast-props-gnome-backend.json` | **Real**: `--auto-start=no get-property <name> /org/freedesktop/portal/desktop <ScreenCast interface> version AvailableSourceTypes AvailableCursorModes` (one JSON line per property) |
| `mutter-screencast-version.json` | **Real**: `get-property org.gnome.Mutter.ScreenCast /org/gnome/Mutter/ScreenCast org.gnome.Mutter.ScreenCast Version` on GNOME 50.1 |
