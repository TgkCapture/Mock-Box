from flask import Blueprint, jsonify

from .. import generators
from ..controls import count_arg, now, rng

bp = Blueprint("orders", __name__)


@bp.get("/orders")
def list_orders():
    return jsonify(generators.orders(rng(), now(), count_arg(3)))
