from flask import Blueprint

from .. import generators
from ..controls import rng
from ..listing import list_response

bp = Blueprint("products", __name__)


@bp.get("/products")
def list_products():
    return list_response(lambda n: generators.products(rng(), n), 5)
