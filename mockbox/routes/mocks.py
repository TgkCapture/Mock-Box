"""Status of user-defined custom routes."""

from flask import Blueprint, jsonify

from ..custom_routes import get_custom_routes

bp = Blueprint("mocks", __name__)


@bp.get("/mocks")
def mocks_status():
    custom = get_custom_routes()
    custom.maybe_reload()
    return jsonify(custom.status())
