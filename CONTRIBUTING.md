# Contributing

Thanks for helping improve Mock-Box! Bug reports, new mock resources and documentation fixes
are all welcome.

## Setup

```bash
git clone https://github.com/TgkCapture/mock-box.git
cd mock-box
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Adding a mock endpoint

1. **Generator.** Add a function to `mockbox/generators.py` that takes a `random.Random`, plus
   `now` if it produces timestamps. Use only that RNG, never the global `random` module, so
   `?seed=` stays reproducible.
2. **Route.** Create `mockbox/routes/<resource>.py` with a `bp = Blueprint(...)`. Read sizes with
   `count_arg(default)` and pass in `rng()` / `now()` from `mockbox.controls`.
3. **Register.** Add the blueprint to `MOCK_BLUEPRINTS` in `mockbox/routes/__init__.py`. That
   also gives the endpoint `?count/?seed/?delay/?status`.
4. **Document.** Add the path to `mockbox/openapi.py` and to the table in `README.md`.
   `tests/test_openapi.py` fails until the spec matches the routes.
5. **Test.** Add cases to `tests/test_mock_data.py`. The parametrized seed and count tests only
   need a new entry.

To protect a route, use `@require_auth()` for any scheme, or `@require_auth("jwt")`,
`"bearer"`, `"api_key"` or `"basic"` for specific ones. The resolved context is on `flask.g.auth`.

## Guidelines

- Keep runtime dependencies to a minimum (currently Flask and PyJWT).
- Return errors by raising `mockbox.errors.ApiError(status, message)` so every response uses the same JSON shape.
- Don't add anything that writes to the user's files or reaches out to the network at runtime.
- Make sure `pytest` passes before opening a pull request.

## Reporting security issues

Mock-Box is deliberately permissive. Accepting any Basic credentials and handing out tokens to
anyone are features, not bugs. If you find a problem that matters even for a local testing tool
(for example, code execution or reading files through a request), please report it through a
private GitHub security advisory rather than a public issue.
