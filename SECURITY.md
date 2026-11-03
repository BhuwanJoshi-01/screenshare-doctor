# Security Policy

## Supported versions

Only the latest release and the `main` branch receive fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them privately through GitHub instead:
**Security → Report a vulnerability** on this repository
(<https://github.com/BhuwanJoshi-01/screenshare-doctor/security/advisories/new>).

Include what you found, how to reproduce it, and the impact you expect. You will get an answer within a week,
and a fix or mitigation as soon as possible after that.

## What counts as a security problem here

Screenshare Doctor looks at the parts of your desktop that decide what can capture your screen, and its reports
are meant to be shared in public bug trackers. These are in scope:

- **Capture without consent.** No command may open a screen-sharing request, read screen contents or keep a
  PipeWire stream unless you started an interactive test and confirmed it. Doing so anyway is a vulnerability.
- **Changes to your system.** Diagnosis is read-only. Starting, restarting or stopping a service (including
  D-Bus activation of a portal that was not running), editing portal or PipeWire configuration, or needing
  `sudo` is a bug.
- **Leaks in reports.** A report that contains your user name, home directory, window titles, application names
  you did not ask about, device serial numbers or raw logs.
- **Network access.** Normal use makes no network connections.

Bugs in xdg-desktop-portal, its backends, PipeWire, WirePlumber or the compositor should be reported to those
projects.

The GNOME Shell extension runs inside your compositor; problems in it are in scope too.
