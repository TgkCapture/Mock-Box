"""Request history API (/api/inspector/...) and the live /inspect page."""

from flask import Blueprint, jsonify, render_template, request

from ..controls import int_arg
from ..errors import ApiError
from ..inspector import get_inspector

bp = Blueprint("inspector", __name__, url_prefix="/inspector")
page_bp = Blueprint("inspector_page", __name__)


@bp.get("/requests")
def list_requests():
    limit = int_arg("limit", 50, 1, 1000)
    entries = get_inspector().list(limit, request.args.get("method"), request.args.get("path"))
    return jsonify({"requests": entries, "total": len(entries)})


@bp.get("/requests/<int:entry_id>")
def get_request(entry_id: int):
    entry = get_inspector().get(entry_id)
    if entry is None:
        raise ApiError(404, f"No recorded request with id {entry_id}")
    return jsonify(entry)


@bp.delete("/requests")
def clear_requests():
    return jsonify({"cleared": get_inspector().clear()})


@page_bp.get("/inspect")
def inspect_page():
    return render_template("inspect.html")
