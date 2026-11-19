# Releasing

Releases are automated by [`.github/workflows/release.yml`](https://github.com/TgkCapture/mock-box/blob/main/.github/workflows/release.yml).
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
4. **Documentation site.** Go to *Settings → Pages* and set *Source* to **GitHub Actions**. The
   `Docs` workflow then publishes https://tgkcapture.github.io/mock-box/ on every push to `main`
   that touches the docs.
5. **Private vulnerability reporting.** *Settings → Security → Private vulnerability reporting →
   Enable*. `SECURITY.md` points reporters there.
6. **Make the project discoverable.** On the repository page, click the gear next to *About* and set:
   - Description: *Mock API server for testing HTTP clients: realistic data, CRUD, payments, auth
     flows and custom routes. Enable only the features you need.*
   - Website: `https://tgkcapture.github.io/mock-box/`
   - Topics: `mock-server`, `mock-api`, `api-mocking`, `fake-api`, `testing`, `openapi`, `rest-api`,
     `flask`, `python`, `docker`, `jwt`, `oauth2`, `webhooks`, `payments`, `mobile-money`

   Or with the GitHub CLI:

   ```bash
   gh repo edit TgkCapture/mock-box      --description "Mock API server for testing HTTP clients: realistic data, CRUD, payments, auth flows and custom routes. Enable only the features you need."      --homepage "https://tgkcapture.github.io/mock-box/"      --add-topic mock-server,mock-api,api-mocking,fake-api,testing,openapi,rest-api,flask,python,docker,jwt,oauth2,webhooks,payments,mobile-money      --enable-discussions
   ```

   Add a few issues labelled `good first issue` so newcomers have somewhere to start.

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
