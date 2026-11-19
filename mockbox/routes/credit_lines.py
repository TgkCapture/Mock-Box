from flask import Blueprint

from .. import generators
from ..controls import rng
from ..listing import list_response

bp = Blueprint("credit_lines", __name__)


@bp.get("/credit-lines")
def list_credit_lines():
    return list_response(lambda n: generators.credit_lines(rng(), n), 5)
