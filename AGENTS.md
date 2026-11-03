# AGENTS.md

Guide for contributors and coding agents. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the rules in full.

## What this is

A read-only Python CLI that diagnoses screen sharing on Linux Wayland desktops (GNOME first, then KDE Plasma and
Hyprland), starting from the app and the symptom. Plain Python 3.11+, Typer and Rich, packaged with uv
(`uv_build` backend), `src/` layout. A GNOME Shell extension (GJS, GPL-2.0-or-later) will live in `extension/`.

## Commands

```bash
uv sync                                    # create .venv with the dev tools
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q   # what CI runs
uv run pytest -q --cov                     # with coverage
```

## Layout

```
src/screenshare_doctor/
  cli.py          Typer app + main(): exit codes, redacted internal errors (SSD_DEBUG=1 for tracebacks)
  models.py       Status/Severity/Confidence, Layer, Evidence, Finding (codes SSD-<AREA>-<NNN>),
                  ProbeFailure, SessionEnvironment/SessionPaths/LogindFacts/SessionFacts,
                  PackageFacts, ServiceFacts, BusName/PortalObject/DbusFacts, XdgDirectories,
                  PortalDescriptor/PortalsConf/PortalFiles, PipeWireFacts, Snapshot
  orchestrator.py collect_session(), inspect_session/services/dbus/routes(): run the collectors and
                  build the Snapshot (facts only; conclusions are recomputed)
  collectors/     environment.py (allowlisted session variables, stat() of runtime dir and sockets),
                  logind.py (loginctl show-user/show-session only; ids checked before use),
                  packages.py (dpkg-query -W / rpm -q / pacman -Q; manager needs program AND database;
                  files fallback), services.py (systemctl --user show / show-environment, allowlisted),
                  dbus.py (bus daemon: ListActivatableNames + NameHasOwner; then ONLY running names,
                  always busctl --auto-start=no: Introspect, ScreenCast properties)
                  portal_config.py (candidate portals.conf + *.portal files, read-only, 64 KiB cap),
                  pipewire.py (pw-dump per object type, ONLY if pipewire.service is active: socket
                  activation would start it; reduced to counters + known client names)
  screencast.py   names for the ScreenCast source-type and cursor-mode bit masks
  keyfile.py      GKeyFile rules (last duplicate wins, bad line = whole file ignored, ; lists)
  portal_files.py .portal / portals.conf judged like register_portal() and the config loader
  portal_paths.py the frontend's search order from the XDG variables (user manager's, not the shell's)
  routes.py       resolve_route(): the selection rules PER RELEASE (<1.17, 1.17-1.18, 1.19-1.21.0,
                  1.20.1 descriptor dirs, 1.21.1 fall-through); observe_route(): prediction vs bus.
                  Read docs/portal-routing.md before changing it.
  desktops.py     XDG_CURRENT_DESKTOP parsed exactly as xdg-desktop-portal does; desktop family
  session.py      assess_session(): session kind (wayland/x11/none/unknown) + where the tool runs
  reports/        terminal.py: render_session/services/dbus/route() (plain Text, never Rich markup
                  from collected data)
  runner.py       CommandRunner protocol, SubprocessRunner (no shell, timeout kills the process group,
                  capped output), probe_failure()
  privacy.py      strip_control(), RedactionContext, Redactor, redact_snapshot()
  exit_codes.py   ExitCode: 0 ok, 1 strict, 2 error, 3 context unavailable, 130 interrupted
tests/
  conftest.py     autouse no_network guard (UNIX sockets allowed); HYPOTHESIS_PROFILE=thorough
  fakes.py        FakeRunner: scripted commands only, anything else fails the test; read_fixture(),
                  read_env_fixture()
  scenarios.py    whole machines replayed from real captures (script_gnome_bus, script_gnome_machine,
                  gnome_file_access)
  fixtures/       real and synthetic captures, each set with a README saying which is which
  unit/           unit tests on fixtures (no session, D-Bus or PipeWire needed)
docs/             roadmap.md (requirement IDs WLD-001 …), cli.md (command reference),
                  portal-routing.md (search order and the per-release selection rules)
.github/          CI, issue forms, PR template
```

The core (runner, privacy, models, CLI shell) was ported from gpu-stack-inspector; each project keeps its own
copy on purpose.

## Rules that are easy to break

- **Passive by default.** No portal request, no screen picker, no capture, no service start/restart/stop, no
  config edits. D-Bus: check `NameHasOwner` first and query with `busctl --user --auto-start=no` so a stopped
  portal is never activated by a property read.
- Never connect to a socket-activated service that is not running: `pw-dump` only runs when
  `pipewire.service` is active.
- No `sudo`, no network access.
- Subprocesses: argument lists only (no `shell=True`), always a timeout and an output cap, always through the
  command runner so tests can fake them.
- The route resolver and rules are pure functions; they never run commands or read files.
- Desktop defaults (GNOME → gnome backend, KDE → kde, Hyprland → hyprland + gtk) are expectations, not pass/fail.
- A failed or missing probe yields `unknown`, never `pass`.
- Redact before serializing (user names, home paths, window titles, app names nobody asked about).
- Finding codes are `SSD-*`; requirement IDs are `WLD-0xx`.
- Tests first where possible: `@pytest.mark.xfail(strict=True, reason="WLD-0xx")`, then implement and drop the
  marker.

## Commits

One logical change per commit; imperative subject of at most 72 characters; a body that explains why; a
`Refs: WLD-0xx` trailer when a requirement applies. Every commit passes the CI command above.
