"""Human-facing pages and service endpoints."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template

from .. import __version__
from ..openapi import build_spec

bp = Blueprint("pages", __name__)

SWAGGER_UI_VERSION = "5.17.14"


def _spec():
    if "mockbox.openapi" not in current_app.extensions:
        current_app.extensions["mockbox.openapi"] = build_spec(__version__)
    return current_app.extensions["mockbox.openapi"]


@bp.get("/")
def home():
    endpoints = [
        {"method": method.upper(), "path": path, "summary": op["summary"], "tag": op["tags"][0], "secured": bool(op["security"])}
        for path, ops in _spec()["paths"].items()
        for method, op in ops.items()
    ]
    return render_template("home.html", endpoints=endpoints, version=__version__)


@bp.get("/docs")
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
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })
