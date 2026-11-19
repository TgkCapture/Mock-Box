"""Generic data endpoint selected by ``?type=``."""

from flask import Blueprint, jsonify, request

from .. import generators
from ..controls import count_arg, rng
from ..errors import ApiError

bp = Blueprint("data", __name__)

DATA_TYPES = {
    "numbers": (50, generators.phone_numbers),
    "names": (10, generators.names),
}


@bp.get("/data")
def get_data():
    data_type = request.args.get("type", "")
    if data_type not in DATA_TYPES:
        raise ApiError(400, f"Unknown data type {data_type!r}; expected one of: {', '.join(DATA_TYPES)}")
    default_count, generate = DATA_TYPES[data_type]
    return jsonify(generate(rng(), count_arg(default_count)))
