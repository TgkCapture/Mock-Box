from flask import Blueprint, jsonify

from .. import generators
from ..controls import count_arg, now, rng

bp = Blueprint("users", __name__)


@bp.get("/users")
def list_users():
    return jsonify(generators.users(rng(), now(), count_arg(4)))
