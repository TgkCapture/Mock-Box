from flask import Blueprint

from .. import generators
from ..controls import now, rng
from ..listing import list_response

bp = Blueprint("activities", __name__)


@bp.get("/user-activities")
def list_user_activities():
    return list_response(lambda n: generators.user_activities(rng(), now(), n), 10)
