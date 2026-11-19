"""Human-facing pages and service endpoints.

``bp`` (always on): ``/``, ``/health`` and ``/openapi.json``.
``docs_bp`` (the "docs" feature): ``/docs``. Without it, ``/`` returns a JSON index instead of HTML.
"""

import copy
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template

from .. import __version__
from ..custom_routes import get_custom_routes
from ..features import FEATURES
from ..openapi import build_spec, custom_route_paths, prune_tags

bp = Blueprint("pages", __name__)
docs_bp = Blueprint("docs", __name__)

SWAGGER_UI_VERSION = "5.17.14"


def _features():
    return current_app.config["MOCKBOX_SETTINGS"].features


def _spec():
    """Spec of the enabled built-in features plus the currently loaded custom routes."""
    if "mockbox.openapi" not in current_app.extensions:
        current_app.extensions["mockbox.openapi"] = build_spec(__version__, _features())
    spec = copy.deepcopy(current_app.extensions["mockbox.openapi"])
    custom = get_custom_routes()
    custom.maybe_reload()
    for path, ops in custom_route_paths(custom.routes).items():
        spec["paths"].setdefault(path, {}).update(ops)  # custom routes override built-ins
    return prune_tags(spec)


@bp.get("/")
def home():
    if "docs" not in _features():
        return jsonify({
            "service": "mock-box",
            "version": __version__,
            "features": list(_features()),
            "openapi": "/openapi.json",
            "health": "/health",
        })
    endpoints = [
        {"method": method.upper(), "path": path, "summary": op["summary"], "tag": op["tags"][0], "secured": bool(op["security"])}
        for path, ops in _spec()["paths"].items()
        for method, op in ops.items()
    ]
    return render_template("home.html", endpoints=endpoints, version=__version__)


@docs_bp.get("/docs")
def docs():
    return render_template("docs.html", swagger_version=SWAGGER_UI_VERSION)


@bp.get("/openapi.json")
def openapi():
    return jsonify(_spec())


@bp.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "mock-box",
        "version": __version__,
        "features": {name: name in _features() for name in FEATURES},
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })
