# Sample reports

Made with `screenshare-doctor report` from the real captures of the Ubuntu 26.04 / GNOME 50.1 machine in
`tests/fixtures` (time stamp fixed), redacted as every report is:

- [`gnome-healthy.md`](gnome-healthy.md) and [`gnome-healthy.json`](gnome-healthy.json): the machine as it is,
  every check passing.
- [`gnome-screencast-disabled.md`](gnome-screencast-disabled.md): the same machine with a `~/.config` override that
  copies a Hyprland setup and sets `org.freedesktop.impl.portal.ScreenCast=none`, a mistake seen in real reports.
