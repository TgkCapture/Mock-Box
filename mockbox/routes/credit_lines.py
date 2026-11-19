from flask import Blueprint, jsonify

from .. import generators
from ..controls import count_arg, rng

bp = Blueprint("credit_lines", __name__)


@bp.get("/credit-lines")
def list_credit_lines():
    return jsonify(generators.credit_lines(rng(), count_arg(5)))
