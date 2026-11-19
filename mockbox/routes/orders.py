from flask import Blueprint

from .. import generators
from ..controls import now, rng
from ..listing import list_response

bp = Blueprint("orders", __name__)


@bp.get("/orders")
def list_orders():
    return list_response(lambda n: generators.orders(rng(), now(), n), 3)
