"""Admin endpoints. Only usable with a configured admin API key.

Admin keys created here live in memory only; permanent keys belong in config.ini or
MOCKBOX_ADMIN_API_KEYS (the server never writes to your config file).
"""

from flask import Blueprint, jsonify

from ..auth import get_auth_manager, mask, require_admin
from ..errors import ApiError
from .auth import json_object_body

bp = Blueprint("admin", __name__, url_prefix="/admin")

MIN_KEY_LENGTH = 16
MAX_KEY_LENGTH = 128


@bp.get("/api-keys")
@require_admin
def list_admin_keys():
    keys = get_auth_manager().list_admin_keys()
    return jsonify({"admin_api_keys": keys, "total": len(keys)})


@bp.post("/api-keys")
@require_admin
def create_admin_key():
    requested = json_object_body().get("api_key")
    if requested is not None:
        if not isinstance(requested, str) or not MIN_KEY_LENGTH <= len(requested) <= MAX_KEY_LENGTH:
            raise ApiError(400, f"api_key must be a string of {MIN_KEY_LENGTH}-{MAX_KEY_LENGTH} characters")
        if any(ch.isspace() for ch in requested):
            raise ApiError(400, "api_key must not contain whitespace")
    key = get_auth_manager().add_admin_key(requested)
    return jsonify({
        "api_key": key,
        "persisted": False,
        "usage": "Send as 'Authorization: ApiKey <key>' or 'X-API-Key: <key>'",
    }), 201


@bp.delete("/api-keys/<path:api_key>")
@require_admin
def delete_admin_key(api_key):
    result = get_auth_manager().remove_admin_key(api_key)
    if result == "protected":
        raise ApiError(409, "This key is defined in configuration; remove it from config.ini or the environment")
    if result == "missing":
        raise ApiError(404, "Admin API key not found")
    return jsonify({"deleted_key": mask(api_key)})


@bp.get("/tokens")
@require_admin
def list_tokens():
    tokens = get_auth_manager().list_tokens()
    return jsonify({"tokens": tokens, "total": len(tokens)})


@bp.delete("/tokens")
@require_admin
def clear_tokens():
    return jsonify({"cleared": get_auth_manager().clear_tokens()})
