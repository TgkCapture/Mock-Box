---
hide:
  - navigation
---

# Mock-Box

**A mock API server for testing HTTP clients. Install once, switch on only the features you need.**

Give your frontend, mobile app or integration tests a realistic backend before the real one
exists, and reproduce the edge cases a real backend can't easily produce: slow responses,
failed payments, expired tokens, flaky endpoints.

```bash
docker run --rm -p 5000:5000 ghcr.io/tgkcapture/mock-box
# or
pip install "mock-box[server]" && mockbox
```

Then open <http://127.0.0.1:5000> for the endpoint list, or <http://127.0.0.1:5000/docs> to try requests in the browser.

[Get started](getting-started.md){ .md-button .md-button--primary }
[API reference](api-reference.md){ .md-button }

## What's in the box

<div class="grid cards" markdown>

-   **[Mock data](features/mock-data.md)**

    ---

    Users, products, orders, posts, todos and more, with pagination, sorting, filtering,
    search, and `?seed`, `?delay` and `?status` on every request.

-   **[Custom routes](features/custom-routes.md)**

    ---

    Define your own endpoints in YAML or JSON: templated responses, conditions, sequences,
    files and hot reload. No code.

-   **[Stateful CRUD](features/store.md)**

    ---

    An in-memory database that remembers creates, updates and deletes for any collection name.

-   **[Payments](features/payments.md)**

    ---

    Mobile money (Airtel Money, TNM Mpamba, M-Pesa, MTN MoMo style) and cards, with test
    numbers, signed webhooks, refunds and 3-D Secure.

-   **[Authentication](features/auth.md)**

    ---

    API keys, JWTs, OAuth2 with refresh rotation, and Basic auth to test your auth handling.

-   **[Debugging](features/debugging.md)**

    ---

    An echo endpoint and a live request inspector that shows exactly what your app sent.

</div>

## Pick only what you need

Every feature is a switch. Disabled features vanish from routing and from the docs.

```bash
mockbox --features payments              # just the payments API
mockbox --features data,store,docs       # mock data, the CRUD store and the docs UI
mockbox --features -admin,-inspector     # everything except these two
```

See [Configuration](configuration.md) for every option.

!!! warning "A testing tool, not a production server"
    Mock-Box hands out tokens to anyone and accepts any Basic credentials. Keep it on
    `127.0.0.1` or a trusted network.
