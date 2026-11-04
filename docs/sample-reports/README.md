# Sample reports

Made with `screenshare-doctor report` from the real captures of the Ubuntu 26.04 / GNOME 50.1 machine in
`tests/fixtures` (time stamp fixed), redacted as every report is:

- [`gnome-healthy.md`](gnome-healthy.md) and [`gnome-healthy.json`](gnome-healthy.json): the machine as it is,
  every check passing.
- [`gnome-screencast-disabled.md`](gnome-screencast-disabled.md): the same machine with a `~/.config` override that
  copies a Hyprland setup and sets `org.freedesktop.impl.portal.ScreenCast=none`, a mistake seen in real reports.

Captured on real sessions in the validation VMs (written by `screenshare-doctor report` there, kept as they came out;
the tests do not regenerate them):

- [`kde-plasma-fedora45.md`](kde-plasma-fedora45.md): KDE Plasma 6.8.2 on Fedora 45, with `pipewire-utils`
  installed, every check passing.
- [`hyprland-arch.md`](hyprland-arch.md): Hyprland 0.57.1 on Arch Linux, after the portal and PipeWire had been
  started (as they are once an app has shared the screen), every check passing.
