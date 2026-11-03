# Publishing (maintainers)

## One-time setup

1. **PyPI trusted publisher.** Log in at <https://pypi.org>, open *Your projects → Publishing*, and add a *pending
   publisher* for project `screenshare-doctor`: owner `BhuwanJoshi-01`, repository `screenshare-doctor`, workflow
   `release.yml`, environment `pypi`. The first release then creates the project; no API token is ever stored.
2. **GitHub environment.** In the repository settings create an environment named `pypi`. Restricting it to
   protected tags or requiring a reviewer is a good extra safeguard.

## Before a release

- `main` is green, including the `package` job (the wheel installed into an empty environment).
- The integration tests pass on a real session of every desktop listed as tested in the support matrix:

  ```bash
  SSD_INTEGRATION=1 uv run pytest -q tests/integration
  ```

- `CHANGELOG.md`: move the *Unreleased* entries under a new `## X.Y.Z (YYYY-MM-DD)` heading.

## A release

1. Set the version and merge it through a pull request:

   ```bash
   uv version X.Y.Z          # updates pyproject.toml and uv.lock
   ```

2. Tag and create the release from `main` (the release is yours; the workflow only builds and uploads):

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
   awk -v v=X.Y.Z '$0 ~ "^## "v" " {p=1; next} /^## / {p=0} p' CHANGELOG.md > /tmp/notes.md
   gh release create vX.Y.Z --title vX.Y.Z --notes-file /tmp/notes.md
   ```

3. Publishing the release runs `release.yml`: it checks that the tag matches the version, builds the sdist and
   wheel, attaches them to the release and uploads them to PyPI.
4. Check the result in a fresh environment:

   ```bash
   uv tool install screenshare-doctor==X.Y.Z && screenshare-doctor --version && screenshare-doctor doctor
   ```

## Versioning

`0.1.0` is the first validated release. Minor versions add features; until `1.0.0` the CLI may still change, but the
JSON output follows `docs/json-schema-v1.json` and finding codes are never reused (see [the checks](rules.md)).

## The GNOME Shell extension

The extension has its own version (`version` in its `metadata.json`) and is published on extensions.gnome.org (EGO)
by the maintainer, from their account. Each GitHub release also carries the zip.

1. Bump `version` in `extension/screenshare-doctor@bhuwanjoshi-01.github.io/metadata.json` (EGO requires an
   increasing integer) and merge it.
2. Check and pack:

   ```bash
   scripts/test-extension-nested.sh     # enable, preferences, disable in a headless nested shell
   scripts/pack-extension.sh            # dist/screenshare-doctor@bhuwanjoshi-01.github.io.shell-extension.zip
   ```

3. Upload the zip at <https://extensions.gnome.org/upload/> and paste the review notes below.

### Notes for the reviewers

- **Subprocess.** The extension runs one program, the user-installed `screenshare-doctor` command-line tool, with
  `Gio.Subprocess` and `communicate_utf8_async`: never synchronously, never through a shell, only when the user opens
  the menu (no polling, no timers while closed). The arguments are fixed (`doctor --format json`, `report`). It is
  not privileged and needs no `pkexec`; the tool itself is read-only.
- **Cleanup.** `disable()` destroys the indicator, whose `destroy()` cancels a shared `Gio.Cancellable`. Cancelling
  removes the only main-loop source (the 60-second kill timeout of a running check) at once and force-exits a running
  child.
- **Clipboard.** Write only, on an explicit menu action (copy the report, copy the install command); declared in the
  description. Never read.
- **No bundled binaries**, no network access, no telemetry. Settings: one GSettings key (`cli-path`).
- **Session modes.** No `session-modes` key: the extension runs in the user session only and is disabled on the lock
  screen.
- **Shexli** reports one manual-review item, EGO-A-005, for the declared clipboard use.
