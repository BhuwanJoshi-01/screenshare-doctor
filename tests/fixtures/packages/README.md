# Package query fixtures

Output of the read-only package queries for the names in `collectors/packages.py` (`PACKAGES`), with `LC_ALL=C`.

| File | Source |
| --- | --- |
| `dpkg-ubuntu-gnome.stdout`, `.stderr` | **Real**: `dpkg-query -W -f '${Package}\t${Version}\t${db:Status-Abbrev}\n' …` on Ubuntu 26.04 (dpkg 1.23.7), exit code 1 because the KDE, wlr and Hyprland backends are not installed. dpkg-query sorts its output by name |
| `dpkg-odd-states.stdout` | Synthetic: removed (`rc`), half-configured (`iF`), unpacked (`iU`) and reinstall-required (`iiR`) packages |
| `rpm-fedora-gnome.stdout` | Synthetic: `rpm -q --queryformat '%{NAME}\t%{VERSION}-%{RELEASE}\n' …` in the documented format, with `pipewire` installed for two architectures (one line each) |
| `pacman-arch-hyprland.stdout`, `.stderr` | Synthetic: `pacman -Q …` on an Arch Hyprland setup, epoch in the PipeWire version |
| `rpm-fedora45-kde.stdout` | **Real**: the same `rpm -q` query on Fedora 45 with KDE Plasma 6.8.2 (rpm 6.1.0, validation VM), exit code 3; the three missing packages are reported on stdout |
| `pacman-arch-hyprland-0.57.stdout`, `.stderr` | **Real**: `pacman -Q …` on Arch Linux with Hyprland 0.57.1 (pacman 7.1.0, validation VM), exit code 1 |
