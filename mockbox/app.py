"""Application factory."""

from __future__ import annotations

from typing import Optional

from flask import Flask, request

from .auth import EXTENSION_KEY, AuthManager
from .config import Settings, load_settings
from .errors import register_error_handlers

CORS_ALLOW_HEADERS = "Authorization, Content-Type, X-API-Key"
CORS_ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"


def create_app(settings: Optional[Settings] = None, config_path: Optional[str] = None) -> Flask:
    """Build the app. Pass ``settings`` directly (tests) or let them load from config/env."""
    settings = settings or load_settings(config_path)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        DEBUG=settings.debug,
        MOCKBOX_SETTINGS=settings,
    )
    app.json.sort_keys = False
    app.extensions[EXTENSION_KEY] = AuthManager(settings.secret_key, settings.admin_api_keys)

    register_error_handlers(app)
    _register_cors(app, settings.cors_origins)

    from .routes import register_routes

    register_routes(app)
    return app


def _register_cors(app: Flask, origins) -> None:
    if not origins:
        return
    allow_all = "*" in origins

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if not origin:
            return response
        if allow_all:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers.add("Vary", "Origin")
        else:
            return response
        response.headers["Access-Control-Allow-Headers"] = CORS_ALLOW_HEADERS
        response.headers["Access-Control-Allow-Methods"] = CORS_ALLOW_METHODS
        response.headers["Access-Control-Max-Age"] = "600"
        return response
