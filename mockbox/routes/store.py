"""Stateful CRUD over in-memory collections: /api/store/<collection>[/<id>]."""

from functools import wraps

from flask import Blueprint, jsonify, url_for

from ..errors import ApiError
from ..listing import respond_with_items
from ..store import StoreError, get_store
from .auth import json_object_body

bp = Blueprint("store", __name__, url_prefix="/store")


def store_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except StoreError as exc:
            raise ApiError(exc.status, exc.message) from None

    return wrapped


def required_object_body() -> dict:
    data = json_object_body()
    if not data:
        raise ApiError(400, "Request body must be a non-empty JSON object")
    return data


@bp.get("")
def list_collections():
    collections = get_store().collections()
    return jsonify({"collections": [{"name": n, "count": c} for n, c in collections.items()]})


@bp.post("/reset")
def reset():
    get_store().reset()
    return jsonify({"reset": True, "collections": get_store().collections()})


@bp.get("/<collection>")
@store_errors
def list_items(collection):
    return respond_with_items(get_store().list(collection))


@bp.post("/<collection>")
@store_errors
def create_item(collection):
    item = get_store().create(collection, required_object_body())
    location = url_for(".get_item", collection=collection, item_id=str(item["id"]))
    return jsonify(item), 201, {"Location": location}


@bp.delete("/<collection>")
@store_errors
def drop_collection(collection):
    return jsonify({"dropped": collection, "items_removed": get_store().drop(collection)})


@bp.get("/<collection>/<item_id>")
@store_errors
def get_item(collection, item_id):
    return jsonify(get_store().get(collection, item_id))


@bp.put("/<collection>/<item_id>")
@store_errors
def replace_item(collection, item_id):
    return jsonify(get_store().replace(collection, item_id, required_object_body()))


@bp.patch("/<collection>/<item_id>")
@store_errors
def update_item(collection, item_id):
    return jsonify(get_store().update(collection, item_id, required_object_body()))


@bp.delete("/<collection>/<item_id>")
@store_errors
def delete_item(collection, item_id):
    get_store().delete(collection, item_id)
    return "", 204
