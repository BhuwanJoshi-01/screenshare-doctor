## What does this change?

<!-- What and why, from the user's point of view. Link the issue if there is one. -->

Requirement IDs: <!-- e.g. WLD-005, or "none" -->

## How was it tested?

<!-- Unit tests and fixtures added. -->

Real desktops tested: <!-- e.g. GNOME 50 / Ubuntu 26.04, KDE Plasma 6.4 / Fedora 44, or "none" -->

## Impact

- Consent and side effects: <!-- Can this open a portal request, activate or restart a service, or change config? -->
- Privacy: <!-- Can any new field carry a user name, path, window title or log line? How is it redacted? -->
- Compatibility: <!-- Changes to CLI flags, exit codes or the JSON schema? -->
- Follow-up issue: <!-- if anything is left for later -->

## Checklist

- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q` passes
- [ ] Default commands stay passive: no portal prompt, no service activation, no config change
- [ ] Negative cases are tested (missing tool, no D-Bus, timeout, malformed config)
- [ ] CHANGELOG.md, docs and the support matrix updated if behaviour or support changed
