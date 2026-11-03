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

The GNOME Shell extension is versioned and published separately on extensions.gnome.org; see its own section once it
is added.
