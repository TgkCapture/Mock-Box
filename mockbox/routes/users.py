from flask import Blueprint

from .. import generators
from ..controls import now, rng
from ..listing import list_response

bp = Blueprint("users", __name__)


@bp.get("/users")
def list_users():
    return list_response(lambda n: generators.users(rng(), now(), n), 4)
