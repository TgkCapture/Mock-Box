"""Token issuing and verification endpoints (public: anyone can obtain a test token)."""

from flask import Blueprint, g, jsonify, request

from ..auth import JWT_DEFAULT_TTL, JWT_MAX_TTL, get_auth_manager, require_auth
from ..controls import int_arg
from ..errors import ApiError

bp = Blueprint("auth", __name__, url_prefix="/auth")

DEFAULT_JWT_CLAIMS = {"sub": "mock_user_123", "user_id": "mock_user_123", "username": "mock_user", "role": "user"}


def json_object_body() -> dict:
    if not request.get_data():
        return {}
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "Request body must be a JSON object")
    return data


@bp.post("/api-key")
def issue_api_key():
    key = get_auth_manager().issue_api_key()
    return jsonify({"api_key": key, "usage": "Send as 'Authorization: ApiKey <key>' or 'X-API-Key: <key>'"}), 201


@bp.post("/jwt-token")
def issue_jwt():
    claims = {**DEFAULT_JWT_CLAIMS, **json_object_body()}
    ttl = int_arg("expires_in", JWT_DEFAULT_TTL, 1, JWT_MAX_TTL)
    token = get_auth_manager().issue_jwt(claims, ttl)
    return jsonify({"access_token": token, "token_type": "bearer", "expires_in": ttl}), 201


@bp.post("/oauth-token")
def issue_oauth_token():
    """OAuth2-style token endpoint. Accepts form or JSON bodies (RFC 6749 error format)."""
    params = request.form.to_dict() if request.form else json_object_body()
    grant_type = params.get("grant_type", "client_credentials")
    manager = get_auth_manager()

    if grant_type == "client_credentials":
        scope = str(params.get("scope") or "read write")
        return jsonify(manager.issue_oauth_token(scope)), 201
    if grant_type == "refresh_token":
        refresh = params.get("refresh_token")
        if not refresh:
            return jsonify({"error": "invalid_request", "error_description": "refresh_token is required"}), 400
        token = manager.refresh_oauth_token(str(refresh))
        if token is None:
            return jsonify({"error": "invalid_grant", "error_description": "Refresh token is invalid or expired"}), 400
        return jsonify(token), 201
    return jsonify({"error": "unsupported_grant_type", "error_description": f"Unsupported grant_type {grant_type!r}"}), 400


@bp.get("/verify")
@require_auth()
def verify():
    return jsonify({"valid": True, "auth": g.auth.to_dict()})


@bp.get("/jwt-only")
@require_auth("jwt")
def jwt_only():
    return jsonify({"message": "JWT authentication successful", "auth": g.auth.to_dict()})


@bp.get("/api-key-only")
@require_auth("api_key")
def api_key_only():
    return jsonify({"message": "API key authentication successful", "auth": g.auth.to_dict()})


@bp.get("/basic-only")
@require_auth("basic")
def basic_only():
    return jsonify({"message": "Basic authentication successful", "auth": g.auth.to_dict()})
