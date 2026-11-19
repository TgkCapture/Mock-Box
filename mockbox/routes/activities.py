from flask import Blueprint, jsonify

from .. import generators
from ..controls import count_arg, now, rng

bp = Blueprint("activities", __name__)


@bp.get("/user-activities")
def list_user_activities():
    return jsonify(generators.user_activities(rng(), now(), count_arg(10)))
