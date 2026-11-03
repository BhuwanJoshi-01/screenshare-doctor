# Contributing

Thanks for helping! By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). The most useful
contributions right now:

- **Test reports** from real desktops: your distribution, desktop and version, the app you tried to share from
  and what happened. Open a *Test report* issue, even when everything works. KDE Plasma and Hyprland reports are
  especially welcome.
- **Fixtures** for situations the tests don't cover yet (unusual `portals.conf` files, `busctl` or `pw-cli`
  output from other versions). Sanitize them first: no user names, home paths or window titles.
- **Bug reports and pull requests.**

## Development setup

You need [uv](https://docs.astral.sh/uv/). The unit tests run on fixtures; they need no Wayland session, D-Bus or
PipeWire.

```bash
git clone https://github.com/BhuwanJoshi-01/screenshare-doctor.git
cd screenshare-doctor
uv sync
```

Before every commit, run the same checks as CI:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
```

## How the code is organised

The tool is split into layers that only talk in one direction:

1. **CLI** parses arguments and wires the other layers together. No diagnosis logic lives here.
2. **Collectors** read facts: allowlisted session variables, package and user-service state, D-Bus names and
   properties, portal configuration files, PipeWire status. They never decide what a fact means, and they record
   a failure instead of raising when a probe goes wrong.
3. **Snapshot**: an immutable, typed record of the facts, including the unknown ones.
4. **Route resolver and rules** are pure functions. The resolver follows the documented `portals.conf` precedence;
   rules turn the snapshot into findings. Neither runs commands or reads files.
5. **Renderers** produce terminal, JSON or Markdown output, after redaction.

## Rules for changes

- **Passive by default.** No default command may open a portal request or screen picker, read screen contents,
  start/restart/stop a service, D-Bus-activate a service that is not running, or edit configuration. Anything
  active belongs behind an explicit interactive flag that asks for consent.
- **No root.** Nothing may need `sudo`.
- **Subprocesses** take an argument list (never `shell=True`), a timeout and an output limit, and go through the
  command runner so tests can replace them.
- **Expectations are not verdicts.** "GNOME usually uses the gnome backend" is a default to compare against, not a
  pass/fail rule. Other valid configurations must not be reported as broken.
- **Unknown is not pass.** If a probe fails or a fact is missing, the result is `unknown`.
- **Redact before serializing**, in every output format.
- **Don't claim support you haven't tested.** A desktop or distribution is only "supported" in the docs after a
  real test on it.
- **Tests first** where you can: add the tests marked `@pytest.mark.xfail(strict=True, reason="WLD-0xx")`, then
  implement the behaviour and remove the marker.

## Commits and pull requests

- One logical change per commit, with an imperative subject (at most 72 characters) and a body that explains why.
- Mention the requirement ID when there is one, as a `Refs: WLD-005` trailer.
- The pull request template asks on which real desktops you tested; "none" is a fine answer.
