from flask import Blueprint, jsonify

from .. import generators
from ..controls import count_arg, rng

bp = Blueprint("products", __name__)


@bp.get("/products")
def list_products():
    return jsonify(generators.products(rng(), count_arg(5)))
