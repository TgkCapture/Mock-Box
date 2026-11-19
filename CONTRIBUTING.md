# Contributing

Thanks for helping improve Mock-Box! Bug reports, new mock resources and documentation fixes
are all welcome. New here? Look for issues labelled
[`good first issue`](https://github.com/TgkCapture/mock-box/labels/good%20first%20issue).
Everyone taking part is expected to follow the [Code of Conduct](https://github.com/TgkCapture/mock-box/blob/main/CODE_OF_CONDUCT.md).

## Setup

```bash
git clone https://github.com/TgkCapture/mock-box.git
cd mock-box
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,server,yaml]"
pytest
```

## Adding a mock endpoint

1. **Generator.** Add a function to `mockbox/generators.py` that takes a `random.Random`, plus
   `now` if it produces timestamps. Use only that RNG, never the global `random` module, so
   `?seed=` stays reproducible.
2. **Route.** Create `mockbox/routes/<resource>.py` with a `bp = Blueprint(...)`. Read sizes with
   `count_arg(default)` and pass in `rng()` / `now()` from `mockbox.controls`.
3. **Register.** Add the blueprint to the right feature in `FEATURE_BLUEPRINTS` in
   `mockbox/routes/__init__.py` (usually `"data"`). That also gives the endpoint
   `?count/?seed/?delay/?status`. A whole new feature group also needs an entry in
   `mockbox/features.py` (`FEATURES` and, for its path prefix, `_PATH_FEATURES`).
4. **Document.** Add the path to `mockbox/openapi.py` and to the table in `README.md`.
   `tests/test_openapi.py` and `tests/test_features.py` fail until the spec matches the routes
   for every feature combination.
5. **Test.** Add cases to `tests/test_mock_data.py`. The parametrized seed and count tests only
   need a new entry.

To protect a route, use `@require_auth()` for any scheme, or `@require_auth("jwt")`,
`"bearer"`, `"api_key"` or `"basic"` for specific ones. The resolved context is on `flask.g.auth`.

## Guidelines

- Keep runtime dependencies to a minimum (currently Flask and PyJWT).
- Return errors by raising `mockbox.errors.ApiError(status, message)` so every response uses the same JSON shape.
- Don't add anything that writes to the user's files, or that reaches out to the network except to
  URLs the user supplied (such as a payment `callback_url`).
- Make sure `pytest` passes before opening a pull request.

## Documentation site

The site at https://tgkcapture.github.io/mock-box/ is built with MkDocs from `docs/` and from
sections of `README.md` (each `##` section is wrapped in `start:`/`end:` snippet markers,
which are HTML comments, so keep them when editing). Preview it with:

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

It is deployed automatically when changes reach `main`.

## Reporting security issues

See [SECURITY.md](https://github.com/TgkCapture/mock-box/blob/main/SECURITY.md). Please don't open public issues for vulnerabilities.
