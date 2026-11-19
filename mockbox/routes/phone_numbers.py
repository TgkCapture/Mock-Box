"""Phone numbers: the same data behind different authentication requirements."""

from flask import Blueprint, g, jsonify

from .. import generators
from ..auth import require_auth
from ..controls import count_arg, rng

bp = Blueprint("phone_numbers", __name__)

DEFAULT_COUNT = 50


def _numbers():
    return generators.phone_numbers(rng(), count_arg(DEFAULT_COUNT))


@bp.get("/phone-numbers/public")
def public():
    return jsonify({"phone_numbers": _numbers(), "auth_required": False})


@bp.get("/phone-numbers")
@require_auth()
def any_auth():
    return jsonify({"phone_numbers": _numbers(), "auth_required": True, "auth": g.auth.to_dict()})


@bp.get("/phone-numbers/jwt")
@require_auth("jwt")
def jwt_only():
    return jsonify({"phone_numbers": _numbers(), "auth_required": True, "auth": g.auth.to_dict()})


@bp.get("/phone-numbers/api-key")
@require_auth("api_key")
def api_key_only():
    return jsonify({"phone_numbers": _numbers(), "auth_required": True, "auth": g.auth.to_dict()})
