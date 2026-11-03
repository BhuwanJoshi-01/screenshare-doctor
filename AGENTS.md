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
src/screenshare_doctor/   the package
tests/                    unit tests on fixtures (no session, D-Bus or PipeWire needed), fixtures/
docs/roadmap.md           requirement IDs WLD-001 … and what v0.1 includes
.github/                  CI, issue forms, PR template
```

## Rules that are easy to break

- **Passive by default.** No portal request, no screen picker, no capture, no service start/restart/stop, no
  config edits. D-Bus: check `NameHasOwner` first and query with `busctl --user --auto-start=no` so a stopped
  portal is never activated by a property read.
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
