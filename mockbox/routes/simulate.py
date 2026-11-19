"""Error simulation. Any mock endpoint also accepts ``?status=<code>``."""

from flask import Blueprint

from ..errors import ApiError

bp = Blueprint("simulate", __name__)


@bp.get("/error")
def default_error():
    raise ApiError(500, "Simulated error")


@bp.get("/error/<int:code>")
def specific_error(code: int):
    if not 400 <= code <= 599:
        raise ApiError(400, f"Status code must be between 400 and 599, got {code}")
    raise ApiError(code, f"Simulated {code} error")
