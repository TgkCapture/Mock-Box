import base64

import jwt
import pytest

from conftest import ADMIN_KEY, basic
from mockbox.auth import OAUTH_ACCESS_TTL, AuthManager


def api_key(client):
    return client.post("/api/auth/api-key").get_json()["api_key"]


def jwt_token(client, claims=None, **query):
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    return client.post(f"/api/auth/jwt-token?{qs}", json=claims or {}).get_json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_api_key_issue_requires_post(client):
    assert client.get("/api/auth/api-key").status_code == 405
    resp = client.post("/api/auth/api-key")
    assert resp.status_code == 201
    assert resp.get_json()["api_key"].startswith("mock_")


@pytest.mark.parametrize("header", ["Authorization", "X-API-Key"])
def test_api_key_headers(client, header):
    key = api_key(client)
    value = f"ApiKey {key}" if header == "Authorization" else key
    resp = client.get("/api/phone-numbers/api-key?count=1", headers={header: value})
    assert resp.status_code == 200
    assert resp.get_json()["auth"] == {"type": "api_key"}


def test_api_key_scheme_is_case_insensitive(client):
    assert client.get("/api/auth/verify", headers={"Authorization": f"apikey {api_key(client)}"}).status_code == 200


def test_unknown_api_key_rejected(client):
    resp = client.get("/api/auth/verify", headers={"X-API-Key": "mock_nope"})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_missing_credentials(client):
    resp = client.get("/api/phone-numbers")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["message"] == "Authentication required"


def test_jwt_flow(client):
    token = jwt_token(client, {"username": "jane", "role": "admin"})
    resp = client.get("/api/phone-numbers/jwt?count=1", headers=bearer(token))
    assert resp.status_code == 200
    user = resp.get_json()["auth"]["user"]
    assert user["username"] == "jane" and user["role"] == "admin"


def test_jwt_reserved_claims_cannot_be_overridden(client, app):
    token = jwt_token(client, {"exp": 1, "iat": 1})
    claims = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    assert claims["exp"] > claims["iat"] > 1


def test_jwt_expires_in(client, app):
    token = jwt_token(client, expires_in=60)
    claims = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 60


@pytest.mark.parametrize("body", ["[1, 2]", "not json", '"string"'])
def test_jwt_rejects_non_object_body(client, body):
    resp = client.post("/api/auth/jwt-token", data=body, content_type="application/json")
    assert resp.status_code == 400


def test_jwt_signed_with_other_key_rejected(client):
    forged = jwt.encode({"sub": "x", "exp": 9999999999, "iat": 1}, "wrong-key-" + "y" * 32, algorithm="HS256")
    assert client.get("/api/auth/jwt-only", headers=bearer(forged)).status_code == 401


def test_jwt_none_algorithm_rejected(client):
    unsigned = jwt.encode({"sub": "x", "exp": 9999999999, "iat": 1}, None, algorithm="none")
    assert client.get("/api/auth/jwt-only", headers=bearer(unsigned)).status_code == 401


def test_expired_jwt_rejected():
    manager = AuthManager("k" * 32, clock=lambda: 1_000_000)
    token = manager.issue_jwt({"sub": "x"}, ttl=10)
    assert manager.decode_jwt(token) is None


def test_scheme_restrictions(client):
    key = api_key(client)
    token = jwt_token(client)
    assert client.get("/api/auth/jwt-only", headers={"X-API-Key": key}).status_code == 401
    assert client.get("/api/auth/api-key-only", headers=bearer(token)).status_code == 401
    assert client.get("/api/auth/basic-only", headers=bearer(token)).status_code == 401
    # An opaque token is not a JWT
    assert client.get("/api/auth/jwt-only", headers=bearer(key)).status_code == 401


def test_bearer_opaque_token(client):
    resp = client.get("/api/auth/verify", headers=bearer(api_key(client)))
    assert resp.get_json()["auth"] == {"type": "bearer"}


def test_basic_auth_accepts_any_credentials_but_hides_password(client):
    resp = client.get("/api/auth/basic-only", headers=basic("bob", "hunter2"))
    assert resp.status_code == 200
    assert resp.get_json()["auth"]["user"] == {"username": "bob"}
    assert "hunter2" not in resp.get_data(as_text=True)


@pytest.mark.parametrize(
    "value",
    ["Basic !!!notbase64", "Basic " + base64.b64encode(b"nocolon").decode(), "Basic " + base64.b64encode(b":pw").decode(), "Basic"],
)
def test_malformed_basic_rejected(client, value):
    assert client.get("/api/auth/basic-only", headers={"Authorization": value}).status_code == 401


def test_oauth_client_credentials_and_refresh_rotation(client):
    token = client.post("/api/auth/oauth-token", data={"grant_type": "client_credentials", "scope": "read"}).get_json()
    assert token["scope"] == "read" and token["expires_in"] == OAUTH_ACCESS_TTL
    assert client.get("/api/auth/verify", headers=bearer(token["access_token"])).status_code == 200

    new = client.post(
        "/api/auth/oauth-token", data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
    ).get_json()
    assert new["access_token"] != token["access_token"]
    assert new["scope"] == "read"
    # Old pair is revoked
    assert client.get("/api/auth/verify", headers=bearer(token["access_token"])).status_code == 401
    reused = client.post("/api/auth/oauth-token", json={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]})
    assert reused.status_code == 400 and reused.get_json()["error"] == "invalid_grant"
    assert client.get("/api/auth/verify", headers=bearer(new["access_token"])).status_code == 200


def test_refresh_token_is_not_an_access_token(client):
    token = client.post("/api/auth/oauth-token").get_json()
    assert client.get("/api/auth/verify", headers=bearer(token["refresh_token"])).status_code == 401


def test_oauth_errors(client):
    assert client.post("/api/auth/oauth-token", json={"grant_type": "password"}).get_json()["error"] == "unsupported_grant_type"
    assert client.post("/api/auth/oauth-token", json={"grant_type": "refresh_token"}).get_json()["error"] == "invalid_request"


def test_oauth_access_token_expires():
    now = [1_000_000.0]
    manager = AuthManager("k" * 32, clock=lambda: now[0])
    token = manager.issue_oauth_token()
    assert manager.is_valid_token(token["access_token"])
    now[0] += OAUTH_ACCESS_TTL
    assert not manager.is_valid_token(token["access_token"])
    assert manager.refresh_oauth_token(token["refresh_token"]) is not None


def test_admin_key_works_as_regular_credential(client):
    assert client.get("/api/phone-numbers?count=1", headers={"X-API-Key": ADMIN_KEY}).status_code == 200


def test_tokens_are_isolated_per_app(make_app):
    first, second = make_app().test_client(), make_app().test_client()
    key = api_key(first)
    assert second.get("/api/auth/verify", headers={"X-API-Key": key}).status_code == 401


def test_unknown_scheme_name_rejected_at_decoration():
    from mockbox.auth import require_auth

    with pytest.raises(ValueError):
        require_auth("magic")
