"""Blog-style resources: posts, comments and todos (randomly generated, like /api/users)."""

from flask import Blueprint

from .. import generators
from ..controls import now, rng
from ..listing import list_response

bp = Blueprint("content", __name__)


@bp.get("/posts")
def list_posts():
    return list_response(lambda n: generators.posts(rng(), now(), n), 10)


@bp.get("/comments")
def list_comments():
    return list_response(lambda n: generators.comments(rng(), n), 10)


@bp.get("/todos")
def list_todos():
    return list_response(lambda n: generators.todos(rng(), n), 10)
