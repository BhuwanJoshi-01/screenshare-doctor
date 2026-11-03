# JSON output

`screenshare-doctor doctor --format json` and `screenshare-doctor report --format json` print the whole redacted
report as one JSON document. Its shape is fixed by [`json-schema-v1.json`](json-schema-v1.json) (JSON Schema 2020-12);
within schema version 1 fields are only ever added in a new optional object, never removed or renamed, and a test
fails if the code and the schema disagree.

## Reading it

Start with `summary`, which restates the facts in the form most readers want:

```json
{
  "session": "wayland",
  "location": "desktop",
  "desktop_family": "gnome",
  "desktop_name": "gnome",
  "portal_version": "1.21.1+ds-1ubuntu3.1",
  "counts": {"pass": 15, "warn": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "not_tested": 0},
  "worst": "pass"
}
```

(Real values from Ubuntu 26.04 with GNOME 50.1.) `worst` is the most serious status among the findings, in the order
fail, warn, unknown, pass, not tested, not applicable; it is what a status indicator should show.

Then `findings`: one object per check, in evaluation order, with `id` (`SSD-<AREA>-<NNN>`, see
[the checks](rules.md)), `status`, `severity`, `confidence`, `summary`, `reason`, `layer`, `evidence` (source, key,
value), `recommended_action`, `verify_command`, `limitations` and `caused_by` (the root cause it follows from, if any).

The other top-level objects are the facts the checks used, each `null` when that part was not collected:

| Key | What |
| --- | --- |
| `session` | allowlisted session variables, the runtime directory and display sockets, logind's sessions |
| `packages` | the portal, backend, PipeWire and WirePlumber packages and which package manager answered |
| `services` | user unit states and the user manager's allowlisted variables and directories |
| `dbus` | whether the session bus answered, the portal bus names (running, activatable) and what the running ones expose |
| `portal_files` | desktop names, search directories, every `portals.conf` and `.portal` found, unreadable files |
| `pipewire` | version, known clients, counts of other clients and video nodes, or why PipeWire was not asked |
| `probe_failures` | what could not be checked and why |
| `redactions` | how many values of each kind were redacted |

## Stability and privacy

- Values are redacted before serialisation: home paths become `~` (other users' homes `/home/<user>`), user and host
  names are replaced, secret-looking values and tokens are removed. `redactions` says what was changed.
- Nothing outside the documented allowlists is ever collected, so the report cannot contain the rest of your
  environment, application names connected to PipeWire, or a list of installed apps.
- `schema_version` is `1`. An incompatible change would raise it and ship a new schema file.
