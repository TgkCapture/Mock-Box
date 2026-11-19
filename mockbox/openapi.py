"""OpenAPI 3.0 description of the server. Powers /docs and the home page endpoint list.

``tests/test_openapi.py`` fails if a route is added without being documented here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .controls import MAX_COUNT, MAX_DELAY_MS
from .listing import DEFAULT_PER_PAGE, MAX_PER_PAGE

ANY_AUTH = [{"BearerAuth": []}, {"ApiKeyAuth": []}, {"BasicAuth": []}]
ADMIN_AUTH = [{"ApiKeyAuth": []}]

_JSON_OK = {"description": "Success", "content": {"application/json": {}}}
_ERRORS = {
    "400": {"$ref": "#/components/responses/Error"},
}
_AUTH_ERRORS = {
    "401": {"$ref": "#/components/responses/Error"},
}
_ADMIN_ERRORS = {
    "401": {"$ref": "#/components/responses/Error"},
    "403": {"$ref": "#/components/responses/Error"},
}
_LISTING = [
    {"$ref": "#/components/parameters/page"},
    {"$ref": "#/components/parameters/per_page"},
    {"$ref": "#/components/parameters/limit"},
    {"$ref": "#/components/parameters/cursor"},
    {"$ref": "#/components/parameters/sort"},
    {"$ref": "#/components/parameters/filter"},
    {"$ref": "#/components/parameters/q"},
    {"$ref": "#/components/parameters/envelope"},
]
_CONTROLS = [
    {"$ref": "#/components/parameters/count"},
    {"$ref": "#/components/parameters/seed"},
    {"$ref": "#/components/parameters/delay"},
    {"$ref": "#/components/parameters/status"},
]


def _op(
    tag: str,
    summary: str,
    *,
    description: str = "",
    controls: bool = False,
    listing: bool = False,
    security: Optional[List[Dict[str, list]]] = None,
    params: Optional[List[Dict[str, Any]]] = None,
    body: Optional[Dict[str, Any]] = None,
    ok: str = "200",
    extra_errors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    op: Dict[str, Any] = {"tags": [tag], "summary": summary, "responses": {ok: _JSON_OK, **_ERRORS}}
    if description:
        op["description"] = description
    parameters = list(params or []) + (_CONTROLS if controls else []) + (_LISTING if listing else [])
    if parameters:
        op["parameters"] = parameters
    if body:
        op["requestBody"] = body
    op["security"] = security if security is not None else []
    if security:
        op["responses"].update(_AUTH_ERRORS)
    if extra_errors:
        op["responses"].update(extra_errors)
    return op


def _query(name: str, description: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "in": "query", "required": False, "description": description, "schema": schema}


def _json_body(example: Dict[str, Any], description: str) -> Dict[str, Any]:
    return {
        "required": False,
        "description": description,
        "content": {"application/json": {"schema": {"type": "object"}, "example": example}},
    }


def build_spec(version: str) -> Dict[str, Any]:
    paths = {
        # ---------------------------------------------------------------- auth
        "/api/auth/api-key": {"post": _op("Auth", "Issue an API key", ok="201")},
        "/api/auth/jwt-token": {
            "post": _op(
                "Auth",
                "Issue a JWT",
                description="The JSON body is merged into the token claims (exp/iat/nbf are ignored).",
                params=[_query("expires_in", "Lifetime in seconds (default 86400)", {"type": "integer", "minimum": 1})],
                body=_json_body({"username": "jane", "role": "admin"}, "Custom claims"),
                ok="201",
            )
        },
        "/api/auth/oauth-token": {
            "post": _op(
                "Auth",
                "Issue or refresh an OAuth2 token",
                description="grant_type `client_credentials` (default) or `refresh_token`. "
                "Accepts form-encoded or JSON bodies. Refresh tokens rotate on use.",
                body={
                    "required": False,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "grant_type": {"type": "string", "enum": ["client_credentials", "refresh_token"]},
                                    "refresh_token": {"type": "string"},
                                    "scope": {"type": "string"},
                                },
                            }
                        },
                        "application/json": {"schema": {"type": "object"}},
                    },
                },
                ok="201",
            )
        },
        "/api/auth/verify": {"get": _op("Auth", "Verify credentials (any scheme)", security=ANY_AUTH)},
        "/api/auth/jwt-only": {"get": _op("Auth", "Accepts only a JWT", security=[{"BearerAuth": []}])},
        "/api/auth/api-key-only": {"get": _op("Auth", "Accepts only an API key", security=[{"ApiKeyAuth": []}])},
        "/api/auth/basic-only": {"get": _op("Auth", "Accepts only Basic auth", security=[{"BasicAuth": []}])},
        # ---------------------------------------------------------------- admin
        "/api/admin/api-keys": {
            "get": _op("Admin", "List admin API keys (masked)", security=ADMIN_AUTH, extra_errors=_ADMIN_ERRORS),
            "post": _op(
                "Admin",
                "Create an in-memory admin API key",
                security=ADMIN_AUTH,
                body=_json_body({"api_key": "my-own-admin-key-123"}, "Omit api_key to generate one"),
                ok="201",
                extra_errors=_ADMIN_ERRORS,
            ),
        },
        "/api/admin/api-keys/{api_key}": {
            "delete": _op(
                "Admin",
                "Delete a runtime admin API key",
                security=ADMIN_AUTH,
                params=[{"name": "api_key", "in": "path", "required": True, "schema": {"type": "string"}}],
                extra_errors={
                    **_ADMIN_ERRORS,
                    "404": {"$ref": "#/components/responses/Error"},
                    "409": {"$ref": "#/components/responses/Error"},
                },
            )
        },
        "/api/admin/tokens": {
            "get": _op("Admin", "List issued tokens", security=ADMIN_AUTH, extra_errors=_ADMIN_ERRORS),
            "delete": _op("Admin", "Revoke all issued tokens", security=ADMIN_AUTH, extra_errors=_ADMIN_ERRORS),
        },
        # ---------------------------------------------------------------- mock data
        "/api/phone-numbers/public": {"get": _op("Mock data", "Phone numbers (no auth)", controls=True)},
        "/api/phone-numbers": {"get": _op("Mock data", "Phone numbers (any auth)", controls=True, security=ANY_AUTH)},
        "/api/phone-numbers/jwt": {
            "get": _op("Mock data", "Phone numbers (JWT only)", controls=True, security=[{"BearerAuth": []}])
        },
        "/api/phone-numbers/api-key": {
            "get": _op("Mock data", "Phone numbers (API key only)", controls=True, security=[{"ApiKeyAuth": []}])
        },
        "/api/data": {
            "get": _op(
                "Mock data",
                "Data selected by type",
                controls=True,
                params=[
                    {
                        "name": "type",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "enum": ["numbers", "names"]},
                    }
                ],
            )
        },
        "/api/products": {"get": _op("Mock data", "Products", controls=True, listing=True)},
        "/api/users": {"get": _op("Mock data", "Users", controls=True, listing=True)},
        "/api/orders": {"get": _op("Mock data", "Orders", controls=True, listing=True)},
        "/api/credit-lines": {"get": _op("Mock data", "Credit lines", controls=True, listing=True)},
        "/api/user-activities": {"get": _op("Mock data", "User activities", controls=True, listing=True)},
        "/api/rss-feed": {
            "get": _op(
                "Mock data",
                "RSS feed (JSON or XML)",
                controls=True,
                params=[_query("format", "Response format", {"type": "string", "enum": ["json", "xml"]})],
            )
        },
        "/api/error": {"get": _op("Errors", "Always returns 500", controls=True, ok="500")},
        "/api/error/{code}": {
            "get": _op(
                "Errors",
                "Returns the given status code (400-599)",
                controls=True,
                params=[{"name": "code", "in": "path", "required": True, "schema": {"type": "integer"}}],
                ok="default",
            )
        },
        # ---------------------------------------------------------------- service
        "/health": {"get": _op("Service", "Health check")},
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Mock-Box",
            "version": version,
            "description": "Mock API server for testing HTTP clients. Every *Mock data* endpoint accepts "
            "`count`, `seed`, `delay` and `status` query parameters.",
            "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        },
        "tags": [
            {"name": "Mock data"},
            {"name": "Auth", "description": "Obtain test credentials, then click Authorize."},
            {"name": "Admin", "description": "Requires an admin API key from configuration."},
            {"name": "Errors"},
            {"name": "Service"},
        ],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "description": "JWT, API key or OAuth access token"},
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "BasicAuth": {"type": "http", "scheme": "basic", "description": "Any username/password is accepted"},
            },
            "parameters": {
                "page": _query("page", "Page number (enables page pagination)", {"type": "integer", "minimum": 1}),
                "per_page": _query("per_page", f"Items per page (1-{MAX_PER_PAGE}, default {DEFAULT_PER_PAGE})", {"type": "integer", "minimum": 1, "maximum": MAX_PER_PAGE}),
                "limit": _query("limit", "Items per page (enables cursor pagination)", {"type": "integer", "minimum": 1, "maximum": MAX_PER_PAGE}),
                "cursor": _query("cursor", "Cursor from a previous response's X-Next-Cursor / meta.next_cursor", {"type": "string"}),
                "sort": _query("sort", "Comma-separated fields; prefix with - for descending, e.g. -price,name", {"type": "string"}),
                "filter": {
                    "name": "filter",
                    "in": "query",
                    "required": False,
                    "style": "deepObject",
                    "explode": True,
                    "description": "filter[field]=a,b (any of) or filter[field][op]=value with op in eq, ne, gt, gte, lt, lte, contains",
                    "schema": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "q": _query("q", "Case-insensitive search across text fields", {"type": "string"}),
                "envelope": _query("envelope", "Wrap the result as {data, meta, links}", {"type": "boolean"}),
                "count": _query("count", f"Number of items (1-{MAX_COUNT})", {"type": "integer", "minimum": 1, "maximum": MAX_COUNT}),
                "seed": _query("seed", "Reproducible output for the same seed", {"type": "string", "maxLength": 64}),
                "delay": _query("delay", f"Delay in ms (0-{MAX_DELAY_MS})", {"type": "integer", "minimum": 0, "maximum": MAX_DELAY_MS}),
                "status": _query("status", "Force an error response (400-599)", {"type": "integer", "minimum": 400, "maximum": 599}),
            },
            "responses": {
                "Error": {
                    "description": "Error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "integer"},
                                            "type": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    }
                                },
                            }
                        }
                    },
                }
            },
        },
    }
