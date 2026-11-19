"""Optional feature groups. Run only what you need with ``--features`` / ``MOCKBOX_FEATURES``.

Examples::

    mockbox                              # everything (default)
    mockbox --features payments          # only the payments API (plus /health, /openapi.json)
    mockbox --features data,store,docs   # mock data, the CRUD store and the docs UI
    mockbox --features -payments,-admin  # everything except payments and the admin API

Custom routes (``--mocks``), ``/health``, ``/openapi.json`` and ``/api/mocks`` are always on.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

# name -> one-line description (shown in --help, /health and the docs).
FEATURES = {
    "data": "Generated mock data (users, products, orders, posts, ...), request controls and /api/error",
    "store": "Stateful CRUD store at /api/store",
    "payments": "Simulated mobile money and card payments at /api/payments",
    "auth": "Test credentials: API keys, JWTs and OAuth2 tokens at /api/auth",
    "admin": "Admin API for managing keys and tokens at /api/admin",
    "echo": "Request echo at /api/echo",
    "inspector": "Request history at /api/inspector and the /inspect page",
    "docs": "Home page with the endpoint list and Swagger UI at /docs",
}
ALL: Tuple[str, ...] = tuple(FEATURES)

# Path prefix -> feature, used to filter the OpenAPI spec. Unlisted /api paths belong to "data".
_PATH_FEATURES = (
    ("/api/auth", "auth"),
    ("/api/admin", "admin"),
    ("/api/store", "store"),
    ("/api/payments", "payments"),
    ("/api/echo", "echo"),
    ("/api/inspector", "inspector"),
    ("/api/mocks", None),
    ("/api/", "data"),
)


class FeatureError(ValueError):
    pass


def parse_features(value: Iterable[str] | str) -> Tuple[str, ...]:
    """Parse ``"data,store"``, ``"all"``, ``"-payments"`` or ``"all,-docs"`` into feature names.

    A list made only of exclusions starts from all features.
    """
    items = [i.strip().lower() for i in (value.split(",") if isinstance(value, str) else value) if i.strip()]
    if not items:
        raise FeatureError(f"no features given; choose from: all, {', '.join(ALL)}")
    included = [i for i in items if not i.startswith("-")]
    excluded = [i[1:] for i in items if i.startswith("-")]
    unknown = sorted({i for i in included + excluded if i not in FEATURES and i != "all"})
    if unknown:
        raise FeatureError(f"unknown feature(s) {unknown}; choose from: all, {', '.join(ALL)}")
    selected = set(ALL) if not included or "all" in included else set(included)
    return tuple(f for f in ALL if f in selected and f not in excluded)


def feature_for_path(path: str) -> Optional[str]:
    """The feature a documented path belongs to, or None for always-on paths."""
    for prefix, feature in _PATH_FEATURES:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return feature
    return None
