# Package query fixtures

Output of the read-only package queries for the names in `collectors/packages.py` (`PACKAGES`), with `LC_ALL=C`.

| File | Source |
| --- | --- |
| `dpkg-ubuntu-gnome.stdout`, `.stderr` | **Real**: `dpkg-query -W -f '${Package}\t${Version}\t${db:Status-Abbrev}\n' …` on Ubuntu 26.04 (dpkg 1.23.7), exit code 1 because the KDE, wlr and Hyprland backends are not installed. dpkg-query sorts its output by name |
| `dpkg-odd-states.stdout` | Synthetic: removed (`rc`), half-configured (`iF`), unpacked (`iU`) and reinstall-required (`iiR`) packages |
| `rpm-fedora-gnome.stdout` | Synthetic: `rpm -q --queryformat '%{NAME}\t%{VERSION}-%{RELEASE}\n' …` in the documented format, with `pipewire` installed for two architectures (one line each) |
| `pacman-arch-hyprland.stdout`, `.stderr` | Synthetic: `pacman -Q …` on an Arch Hyprland setup, epoch in the PipeWire version |
