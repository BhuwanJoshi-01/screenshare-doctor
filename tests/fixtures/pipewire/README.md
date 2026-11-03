# PipeWire fixtures

Output of `pw-dump -N -i 0 PipeWire:Interface:<Type>`, **real** captures from Ubuntu 26.04 (PipeWire 1.6.2,
WirePlumber 0.5.13) in a GNOME 50.1 session, reduced to the fields the parser reads:

| File | Kept | Removed |
| --- | --- | --- |
| `pw-dump-core-ubuntu.json` | `version`, `name`, three core properties | user and host name (set to `user`/`host`), cookie, other properties |
| `pw-dump-clients-ubuntu.json` | `application.name` of PipeWire, WirePlumber, gnome-shell, Mutter, xdg-desktop-portal, pw-dump | every other application name (replaced with `other-app`), all other properties |
| `pw-dump-nodes-ubuntu.json` | `media.class`, `device.api`, `factory.name` | node names, descriptions, formats and parameters |

The machine had a webcam (one `Video/Source` from v4l2) and no screen cast running.
