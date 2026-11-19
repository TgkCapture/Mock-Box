# Mock-Box

[![Tests](https://github.com/TgkCapture/mock-box/actions/workflows/tests.yml/badge.svg)](https://github.com/TgkCapture/mock-box/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Mock-Box is a small mock API server for testing HTTP clients. It returns realistic JSON
for common resources, simulates real authentication flows (API keys, JWT, OAuth2 and Basic),
and lets every request control its own size, randomness, latency and failure mode. Use it
while the real backend doesn't exist yet, or when you need to test edge cases the real
backend can't easily produce.

- **Realistic mock data**: users, products, orders, credit lines, activity logs, phone numbers and an RSS feed (JSON or XML).
- **Controls on every request**: `?count=`, `?seed=` for reproducible output, `?delay=` for latency, and `?status=` to force errors.
- **Auth flows to test against**: issue tokens, then call endpoints that accept any scheme or exactly one.
- **Built-in interactive docs** at `/docs` (Swagger UI) and an OpenAPI spec at `/openapi.json`.
- **CORS enabled**, so a browser app on another port can call it directly.

> **Mock-Box is a testing tool, not a production server.** It hands out tokens to anyone
> and accepts any Basic credentials. Keep it on `127.0.0.1` or a trusted network.

## Quick start

**Docker** (no Python needed):

```bash
docker run --rm -p 5000:5000 ghcr.io/tgkcapture/mock-box
```

**pip** (Python 3.10+):

```bash
pip install "mock-box[server]"
mockbox
```

**From source:**

```bash
git clone https://github.com/TgkCapture/mock-box.git && cd mock-box
pip install -e ".[server]"
mockbox                          # or: python -m mockbox
```

Open http://127.0.0.1:5000 to see the endpoint list, or http://127.0.0.1:5000/docs to try requests in the browser.

The `server` extra installs [waitress](https://docs.pylonsproject.org/projects/waitress/), a
production-grade server. Without it, Mock-Box falls back to Flask's development server.
`--debug` always uses Flask's server.

### Docker

```bash
# Configure with environment variables...
docker run --rm -p 5000:5000 \
  -e MOCKBOX_SECRET_KEY=$(openssl rand -hex 32) \
  -e MOCKBOX_ADMIN_API_KEYS=my-admin-key-1234567890 \
  ghcr.io/tgkcapture/mock-box

# ...or mount a config file
docker run --rm -p 5000:5000 -v "$PWD/config.ini:/app/config.ini:ro" ghcr.io/tgkcapture/mock-box
```

To run it alongside your app, see [`docker-compose.yml`](docker-compose.yml). Images are
published for `linux/amd64` and `linux/arm64`. Each release is tagged with its version
(`0.2.0`, `0.2`) and `latest`.

```bash
curl "http://127.0.0.1:5000/api/users?count=2&seed=demo"
```

### Command line

```text
mockbox [--config PATH] [--host HOST] [--port PORT] [--mocks FILE ...] [--debug | --no-debug] [--version]
```

## Configuration

Every setting is optional. They are read in this order, later sources winning:
built-in defaults, then `config.ini` (in the current directory, or the path given by `--config` or
`MOCKBOX_CONFIG`), then environment variables, then command-line flags.

```bash
cp config.ini.example config.ini
```

| `config.ini`                  | Environment variable     | Default     | Description |
|-------------------------------|--------------------------|-------------|-------------|
| `[server] host`               | `MOCKBOX_HOST`           | `127.0.0.1` | Interface to bind. |
| `[server] port`               | `MOCKBOX_PORT`           | `5000`      | Port to listen on. |
| `[server] debug`              | `MOCKBOX_DEBUG`          | `false`     | Flask debug mode. Never enable it on a non-loopback host. |
| `[server] secret_key`         | `MOCKBOX_SECRET_KEY`     | random      | Signs JWTs. If empty, a random key is used and tokens stop working after a restart. |
| `[server] cors_origins`       | `MOCKBOX_CORS_ORIGINS`   | `*`         | Comma-separated allowed origins. Empty disables CORS. |
| `[auth] admin_api_keys`       | `MOCKBOX_ADMIN_API_KEYS` | *(none)*    | Comma-separated admin keys. If empty, the admin API is disabled. |
| `[mocks] files`               | `MOCKBOX_MOCKS`          | *(none)*    | Comma-separated [custom route](#custom-routes) files. |

Generate a secret key with `python -c "import secrets; print(secrets.token_hex(32))"`.

## Mock data endpoints

All of these are `GET` requests and accept the [request controls](#request-controls).

| Endpoint                     | Default count | Returns |
|------------------------------|---------------|---------|
| `/api/users`                 | 4  | `id`, `name`, `email`, `phone`, `joined_date` |
| `/api/products`              | 5  | `id`, `name`, `category`, `price`, `in_stock` |
| `/api/orders`                | 3  | `order_id`, `user_id`, `product_id`, `product`, `quantity`, `unit_price`, `total_price`, `status`, `order_date` |
| `/api/credit-lines`          | 5  | `credit_line_id`, `customer_name`, `credit_limit`, `balance`, `available_credit`, `status` |
| `/api/user-activities`       | 10 | `activity_id`, `user_id`, `activity_type`, `timestamp` (newest first) |
| `/api/posts`                 | 10 | `id`, `user_id`, `title`, `body`, `published`, `created_at` |
| `/api/comments`              | 10 | `id`, `post_id`, `name`, `email`, `body` |
| `/api/todos`                 | 10 | `id`, `user_id`, `title`, `completed` |
| `/api/rss-feed`              | 5  | A feed channel with items. Add `?format=xml` for real RSS 2.0 XML. |
| `/api/data?type=numbers`     | 50 | A list of phone numbers |
| `/api/data?type=names`       | 10 | A list of `{id, name}` objects |
| `/api/phone-numbers/public`  | 50 | Phone numbers, no auth required |
| `/api/phone-numbers`         | 50 | Same data, requires any auth |
| `/api/phone-numbers/jwt`     | 50 | Same data, requires a JWT |
| `/api/phone-numbers/api-key` | 50 | Same data, requires an API key |
| `/api/error`                 | —  | Always returns `500` |
| `/api/error/{code}`          | —  | Returns the given status code (400–599) |

Phone numbers use the Malawi TNM format (`+26588xxxxxxx`). Timestamps are ISO 8601 in UTC (`2025-01-01T00:00:00Z`).

### Request controls

| Parameter | Range        | Effect |
|-----------|--------------|--------|
| `count`   | 1–1000       | Number of items to generate. |
| `seed`    | 1–64 chars   | Makes the output reproducible: the same seed always returns the same body, timestamps included (they're measured from a fixed reference date). |
| `delay`   | 0–10000 ms   | Waits before responding, for testing loading states and timeouts. |
| `status`  | 400–599      | Skips the endpoint and returns that error, e.g. `?status=503`. |

Invalid values return `400`. Errors always use the same JSON shape:

```json
{ "error": { "status": 503, "type": "Service Unavailable", "message": "Simulated 503 response (requested via ?status=503)" } }
```

Controls are applied before authentication, so `?status=` works on protected endpoints too.

### Pagination, sorting and filtering

All list endpoints (users, products, orders, credit lines, user activities, posts, comments, todos
and every `/api/store` collection) also support the parameters below. If you don't pass any of them, the response is a plain array, as before.

| Parameter | Example | Effect |
|-----------|---------|--------|
| `page`, `per_page` | `?page=2&per_page=10` | Page-based pagination (`per_page` 1–100, default 10). |
| `limit`, `cursor`  | `?limit=10&cursor=bzoxMA` | Cursor-based pagination. Take the next cursor from `X-Next-Cursor` or `meta.next_cursor`. |
| `sort`    | `?sort=-price,name` | Sort by one or more fields. Prefix a field with `-` for descending. |
| `filter[field]` | `?filter[status]=active,overdue` | Exact match. Commas mean "any of". |
| `filter[field][op]` | `?filter[price][gte]=100` | Operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`. |
| `q`       | `?q=banda` | Case-insensitive search across text fields. |
| `envelope`| `?envelope=true` | Return `{"data": [...], "meta": {...}, "links": {...}}` instead of a bare array. |

When paginating:
- **Collection size:** `count` sets the total number of items (default 100).
- **Stable pages:** the collection doesn't change between requests, so pages never overlap. Add `seed` to choose which data you get.
- **Response headers:** `X-Total-Count`, `X-Page`, `X-Per-Page`, `X-Total-Pages` and a GitHub-style `Link` header (`first`, `prev`, `next`, `last`). Cursor mode sends `X-Next-Cursor` instead.
- **Browser access:** CORS exposes these headers, so browser code can read them.

```bash
curl -i "http://127.0.0.1:5000/api/orders?page=2&per_page=5&sort=-total_price&filter[status]=paid"
```

## Custom routes

Describe your own endpoints in a JSON or YAML file and Mock-Box serves them. They can live at
any path, such as `/v1/payments/{id}`, and can even override a built-in endpoint.

```bash
mockbox --mocks mocks.yaml                     # repeat --mocks for several files
# or: [mocks] files = mocks.yaml in config.ini, or MOCKBOX_MOCKS=mocks.yaml
```

```yaml
routes:
  - path: /v1/customers/{id}
    body:
      id: "{{params.id}}"
      name: "{{name}}"
      email: "{{email}}"
      balance: "{{random.float(0, 5000)}}"

  - path: /v1/customers
    body:
      data:
        $repeat: "{{query.limit | 3}}"        # list of N generated items
        item: { id: "{{index}}", name: "{{name}}" }

  - method: POST
    path: /v1/login
    responses:                                 # first matching `when` wins
      - when: { body: { username: admin, password: secret } }
        body: { token: "{{uuid}}" }
    status: 401                                # otherwise
    body: { error: invalid_credentials }

  - path: /v1/flaky
    mode: sequence                             # 503, 503, 200, then repeat
    responses:
      - { status: 503 }
      - { status: 503 }
      - { body: { ok: true } }
```

[`examples/mocks.yaml`](examples/mocks.yaml) is a commented tour of every option. In summary:

| Key | Meaning |
|-----|---------|
| `path` | Required. `{name}` captures a path segment. |
| `method` | `GET` (default), a list such as `[PUT, PATCH]`, or `ANY`. |
| `status`, `headers`, `content_type` | Response status (default 200), headers (templated) and content type. |
| `body` / `body_file` | Inline body (an object or list becomes JSON, a string becomes text), or a file relative to the mocks file. A `.json` file is templated; other files are served as-is. |
| `delay_ms` | Fixed latency, in addition to `?delay=`. |
| `auth` | `any`, or one or more of `jwt`, `bearer`, `api_key`, `basic`. Uses the same credentials as the [built-in auth](#authentication). |
| `responses` + `when` | Conditional responses matched on `query`, `headers`, `params` or `body` (dotted paths). A list means "any of", and `"*"` means "present". |
| `mode: sequence` | Return `responses` in order, then cycle. Useful for testing retries. |
| `description` | Shown in `/docs` and on the home page. |

**Placeholders:**

| Group | Placeholders |
|-------|--------------|
| From the request | `{{params.x}}`, `{{query.x}}`, `{{headers.x}}`, `{{body.a.b}}` |
| Generated | `{{uuid}}`, `{{now}}`, `{{date}}`, `{{timestamp}}`, `{{name}}`, `{{first_name}}`, `{{last_name}}`, `{{email}}`, `{{phone}}`, `{{word}}`, `{{sentence}}`, `{{paragraph}}`, `{{bool}}`, `{{index}}` |
| Random | `{{random.int(1,10)}}`, `{{random.float(0,1)}}`, `{{random.choice(a,b,c)}}` |
| Default value | `{{query.page \| 1}}` (used when the value is missing) |

How placeholders behave:
- **Types are kept** when a string is exactly one placeholder: `"{{random.int(1,9)}}"` renders as a number.
- **Consistent people:** `name`, `first_name`, `last_name` and `email` describe the same generated person within an object.
- **Request controls work too:** `?seed=` makes generated values reproducible, and `?delay=` and `?status=` apply as usual.

**Reloading and errors:**
- **Hot reload:** the file is re-read automatically when it changes. If an edit is invalid, the previous routes stay active and the error is shown at `GET /api/mocks`.
- **Startup errors:** mistakes are reported with their exact location, for example `mocks.yaml: routes[3].status: ...`. Unknown keys are rejected, so typos don't fail silently.
- **YAML support** needs `pip install "mock-box[yaml]"`. The Docker image includes it. In Docker, mount your file and point `MOCKBOX_MOCKS` at it:
  `docker run -p 5000:5000 -v "$PWD/mocks.yaml:/app/mocks.yaml:ro" -e MOCKBOX_MOCKS=/app/mocks.yaml ghcr.io/tgkcapture/mock-box`

## Stateful CRUD (`/api/store`)

`/api/users` and the other mock endpoints return fresh random data on every call. To test
create, update and delete flows, use the store instead. It's a schemaless in-memory database
that remembers your changes.

| Request | Effect |
|---------|--------|
| `GET /api/store` | List collections and their sizes. |
| `GET /api/store/{collection}` | List items. Supports [pagination, sorting and filtering](#pagination-sorting-and-filtering). |
| `POST /api/store/{collection}` | Create an item from any JSON object. Returns `201` with a `Location` header. |
| `GET /api/store/{collection}/{id}` | Get one item. |
| `PUT /api/store/{collection}/{id}` | Replace an item. |
| `PATCH /api/store/{collection}/{id}` | Merge fields into an item. |
| `DELETE /api/store/{collection}/{id}` | Delete an item (`204`). |
| `DELETE /api/store/{collection}` | Drop a whole collection. |
| `POST /api/store/reset` | Restore the seed data and drop any custom collections. |

- **Seeded collections:** `users` (10), `products` (20), `orders` (30), `posts` (20), `comments` (50) and `todos` (40). The seed data is the same on every start.
- **New collections:** `POST` to any new name, for example `/api/store/invoices`, and the collection is created on the spot.
- **IDs:** assigned automatically as integers, unless you send your own `id` (string or integer). A duplicate `id` returns `409`.
- **Timestamps:** `created_at` and `updated_at` are maintained for you.
- **Linking resources:** use filters, for example `GET /api/store/comments?filter[post_id]=3`.
- **Limits:** up to 100 collections and 10,000 items per collection. Data lives in memory, so a restart restores the seed data.

```bash
curl -X POST http://127.0.0.1:5000/api/store/todos -H "Content-Type: application/json" -d '{"title": "Ship v1", "completed": false}'
curl -X PATCH http://127.0.0.1:5000/api/store/todos/41 -H "Content-Type: application/json" -d '{"completed": true}'
```

## Debugging requests

**Echo.** `/api/echo` (and any sub-path, such as `/api/echo/v1/orders`) accepts `GET`, `POST`,
`PUT`, `PATCH` and `DELETE` and returns exactly what it received: method, path, query, headers,
and the body parsed as JSON, form fields, uploaded files (name, type and size) or raw text.

```bash
curl -X POST "http://127.0.0.1:5000/api/echo/webhooks?debug=1" -H "Content-Type: application/json" -d '{"event": "test"}'
```

**Inspector.** Open http://127.0.0.1:5000/inspect for a live list of recent `/api/*` requests,
with headers, body, status and timing. The same data is available as JSON:

| Endpoint | Description |
|----------|-------------|
| `GET /api/inspector/requests` | Recent requests, newest first. Filter with `?limit=`, `?method=` and `?path=`. |
| `GET /api/inspector/requests/{id}` | One recorded request. |
| `DELETE /api/inspector/requests` | Clear the history. |

The history is kept in memory and holds the last 200 requests. Credentials (`Authorization`,
`X-API-Key`, `Cookie`) are masked in the inspector, but not in echo responses, which only go
back to the caller. Request bodies are limited to 10 MB; anything larger gets `413`.

## Authentication

Get a credential from one of the public issuing endpoints, then send it with your request:

| Credential   | How to get it                    | How to send it |
|--------------|----------------------------------|----------------|
| API key      | `POST /api/auth/api-key`         | `Authorization: ApiKey <key>`, `X-API-Key: <key>`, or `Authorization: Bearer <key>` |
| JWT (HS256)  | `POST /api/auth/jwt-token`       | `Authorization: Bearer <jwt>` |
| OAuth2 token | `POST /api/auth/oauth-token`     | `Authorization: Bearer <access_token>` |
| Basic        | Any username and password work   | `Authorization: Basic <base64(user:password)>` |

```bash
# JWT with custom claims, valid for 1 hour
TOKEN=$(curl -s -X POST "http://127.0.0.1:5000/api/auth/jwt-token?expires_in=3600" \
  -H "Content-Type: application/json" -d '{"username": "jane", "role": "admin"}' | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5000/api/auth/verify

# OAuth2: client credentials, then refresh (refresh tokens rotate, so the old pair is revoked)
curl -X POST http://127.0.0.1:5000/api/auth/oauth-token -d grant_type=client_credentials -d scope=read
curl -X POST http://127.0.0.1:5000/api/auth/oauth-token -d grant_type=refresh_token -d refresh_token=<refresh_token>
```

- **JWT:** the JSON body is merged into the token's claims. `exp`, `iat` and `nbf` are ignored, so use `?expires_in=` (seconds, up to 30 days) to set the lifetime.
- **OAuth2:** access tokens expire after 1 hour and refresh tokens after 30 days. Errors follow RFC 6749 (`invalid_grant`, `unsupported_grant_type` and so on).
- **Checking auth:** `GET /api/auth/verify` accepts every scheme and echoes the auth context. `/api/auth/jwt-only`, `/api-key-only` and `/basic-only` each accept exactly one scheme.
- **Missing or bad credentials** return `401` with a `WWW-Authenticate` header.

Issued API keys and OAuth tokens are kept in memory, so a restart clears them. JWTs survive a
restart only if `secret_key` is configured.

## Admin API

Admin endpoints are available only when at least one admin key is configured. They accept
**only** an admin key (`X-API-Key`, `ApiKey` or `Bearer`). Regular tokens, JWTs and Basic
credentials get `403`.

| Endpoint                            | Description |
|-------------------------------------|-------------|
| `GET /api/admin/api-keys`           | List admin keys (masked) and where each came from. |
| `POST /api/admin/api-keys`          | Create a runtime admin key. Body: optional `{"api_key": "..."}` (16–128 characters). |
| `DELETE /api/admin/api-keys/{key}`  | Delete a runtime key. Keys from configuration return `409`. |
| `GET /api/admin/tokens`             | List issued API keys and OAuth tokens. |
| `DELETE /api/admin/tokens`          | Revoke all issued tokens. |

Keys created at runtime last only until the server stops. Mock-Box never writes to your config
file, so to make a key permanent, add it to `admin_api_keys`.

## Web UI

| Path            | What it is |
|-----------------|------------|
| `/`             | Landing page that lists every endpoint (generated from the OpenAPI spec). |
| `/docs`         | Swagger UI: try requests and authorize with any scheme. Loaded from the jsDelivr CDN, so it needs internet access. |
| `/openapi.json` | OpenAPI 3 spec. Import it into Postman, Insomnia or a client generator. |
| `/health`       | Health check. |

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite fails if a route isn't described in `mockbox/openapi.py`, which keeps the docs
accurate. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add an endpoint.

```text
mockbox/
  __main__.py      CLI entry point
  app.py           create_app(): wiring, CORS
  config.py        settings from defaults, config.ini, env vars and flags
  auth.py          token issuing, credential parsing, @require_auth / @require_admin
  controls.py      ?count / ?seed / ?delay / ?status
  generators.py    pure mock-data generators
  openapi.py       OpenAPI spec (drives /docs and the home page)
  errors.py        JSON error format
  routes/          one blueprint per resource
  templates/       home and docs pages
tests/
```

## License

[MIT](LICENSE)
