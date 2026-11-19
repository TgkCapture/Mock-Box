# Releasing

Releases are automated by [`.github/workflows/release.yml`](../.github/workflows/release.yml).
Pushing a `v*` tag runs the tests and then:

- publishes the wheel and sdist to **PyPI** (`pip install mock-box`)
- pushes a multi-arch (amd64/arm64) image to **GHCR** (`ghcr.io/tgkcapture/mock-box:<version>` and `:latest`)
- creates a **GitHub Release** with generated notes and the built files

## One-time setup

1. **PyPI trusted publishing.** No API token is needed. Sign in at https://pypi.org, then go to
   *Your account → Publishing → Add a new pending publisher* and fill in:
   - PyPI project name: `mock-box`
   - Owner: `TgkCapture`, Repository: `mock-box`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. **GitHub environment.** Go to *Settings → Environments → New environment* and name it `pypi`.
   You can also add yourself as a required reviewer, so every PyPI upload waits for your approval.
3. **Make the container image public.** After the first release, open *Packages → mock-box →
   Package settings → Change visibility → Public*. GHCR packages start out private.

## Cutting a release

1. Bump `__version__` in `mockbox/__init__.py`. The workflow refuses a tag that doesn't match it.
2. Move the `Unreleased` notes in `CHANGELOG.md` under the new version heading.
3. Merge to `main`, then run:

   ```bash
   git switch main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

4. Watch the run under *Actions → Release*.
