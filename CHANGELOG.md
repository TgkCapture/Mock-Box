# Changelog

## Unreleased

### Added
- Docker image (`ghcr.io/tgkcapture/mock-box`, amd64/arm64) and a `docker-compose.yml` example.
- `server` extra: when waitress is installed, the `mockbox` CLI serves with it instead of Flask's dev server.
- Release workflow: pushing a `v*` tag publishes to PyPI and GHCR and creates a GitHub Release.
- CI builds and smoke-tests the Docker image.
- Pagination (page-based with `Link`/`X-Total-Count` headers, or cursor-based), sorting, filtering
  (`filter[field]`, `filter[field][op]`), search (`q`) and an optional `{data, meta, links}` envelope
  on list endpoints. Paginated collections are stable across requests.
- CORS now exposes pagination and auth headers to browser code.
- `/api/echo` returns the request back (headers, query, JSON, form, files, raw body).
- Request inspector: live `/inspect` page and `/api/inspector/requests` API with masked credentials.
- Request bodies are limited to 10 MB (`413` beyond that).
- Stateful CRUD store at `/api/store/{collection}`: seeded collections, ad-hoc collections, reset.
- `/api/posts`, `/api/comments` and `/api/todos` mock endpoints.
- Custom routes from JSON/YAML files (`--mocks`): templated bodies, `$repeat`, conditional and
  sequence responses, auth, files, hot reload, shown in `/docs`; status at `/api/mocks`.
- `yaml` extra (PyYAML); the Docker image includes it.

## 0.1.0: first public release

### Breaking changes
- Requires Python 3.10 or newer (3.9 is end-of-life).
- The package is renamed from `app` to `mockbox`. Run it with `mockbox`, `python -m mockbox`, or (still supported) `python mock_server.py`.
- `/api/phone-numbers` now requires authentication. Use `/api/phone-numbers/public` for unauthenticated access.
- `POST /api/auth/api-key` replaces `GET`, because issuing a key changes server state.
- Admin endpoints accept **only** configured admin keys. Previously any credential, including arbitrary Basic credentials, could manage admin keys.
- Admin keys created through the API are kept in memory. The server no longer rewrites `config.ini`.
- `/api/admin/generated-tokens` and `POST /api/admin/clear-tokens` are replaced by `GET` and `DELETE /api/admin/tokens`.
- `/api/auth/protected` is removed. Use `/api/auth/verify`.
- Auth info in responses moved to an `auth` object (`{"type": ..., "user": ...}`).
- The default JWT `role` claim is now `user` (it was `admin`). Pass `{"role": "admin"}` to override it.
- Debug mode defaults to off.
- `/readme` is replaced by `/docs` (Swagger UI) and `/openapi.json`.
- Errors use one JSON shape: `{"error": {"status", "type", "message"}}`.
- Timestamps are ISO 8601 UTC with a `Z` suffix. RSS `pubDate` is real GMT.

### Fixed
- `/api/data?type=names` crashed with a `NameError`.
- An empty `secret_key` signed JWTs with an empty key. A random key is now generated, with a warning.
- The server crashed at startup when `config.ini` was missing. Defaults are now used.
- `requirements.txt` was UTF-16 encoded.
- A custom admin key was silently replaced when it didn't start with `prefix`.
- Credit-line balances could be inconsistent with their status. Order totals didn't match quantity × price.
- `config.ini` and `README.md` were resolved relative to the working directory.
- Invalid JSON bodies caused 500 errors.
- Updated dependencies (Werkzeug 3.0.4 had known security issues).

### Added
- Request controls on all mock endpoints: `count`, `seed` (fully reproducible), `delay` and `status`.
- OAuth2 token expiry, the `refresh_token` grant with rotation, and RFC 6749 error responses.
- `X-API-Key` header support. JWT `?expires_in=`. `WWW-Authenticate` headers on 401s.
- `/api/error/{code}`, and RSS as real XML via `?format=xml`.
- CORS support, configurable with `cors_origins`.
- Environment-variable configuration (`MOCKBOX_*`) and the `mockbox` CLI.
- Interactive docs at `/docs`, an OpenAPI spec, and a home page generated from it.
- A test suite, CI, `pyproject.toml` packaging, and the MIT license.
