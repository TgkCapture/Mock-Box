import pytest

from conftest import ADMIN_KEY, basic

ADMIN_ROUTES = [
    ("get", "/api/admin/api-keys"),
    ("post", "/api/admin/api-keys"),
    ("delete", "/api/admin/api-keys/whatever"),
    ("get", "/api/admin/tokens"),
    ("delete", "/api/admin/tokens"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_requires_credentials(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_regular_credentials_are_not_admin(client, method, path):
    """Previously any Basic credentials or freshly issued API key could manage admin keys."""
    key = client.post("/api/auth/api-key").get_json()["api_key"]
    jwt = client.post("/api/auth/jwt-token", json={"role": "admin"}).get_json()["access_token"]
    for headers in (basic("admin", "admin"), {"X-API-Key": key}, {"Authorization": f"Bearer {jwt}"}):
        assert getattr(client, method)(path, headers=headers).status_code == 403


def test_admin_disabled_without_configured_keys(make_app):
    client = make_app(admin_api_keys=()).test_client()
    resp = client.get("/api/admin/api-keys", headers={"X-API-Key": "anything"})
    assert resp.status_code == 403
    assert "disabled" in resp.get_json()["error"]["message"]


@pytest.mark.parametrize("headers", [{"X-API-Key": ADMIN_KEY}, {"Authorization": f"ApiKey {ADMIN_KEY}"}, {"Authorization": f"Bearer {ADMIN_KEY}"}])
def test_admin_key_header_forms(client, headers):
    assert client.get("/api/admin/api-keys", headers=headers).status_code == 200


def test_list_masks_keys(client, admin_headers):
    keys = client.get("/api/admin/api-keys", headers=admin_headers).get_json()["admin_api_keys"]
    assert keys == [{"key": "test-a...6789", "source": "config"}]
    assert ADMIN_KEY not in str(keys)


def test_runtime_admin_key_lifecycle(client, admin_headers):
    created = client.post("/api/admin/api-keys", headers=admin_headers).get_json()
    new_key = created["api_key"]
    assert created["persisted"] is False
    assert client.get("/api/admin/tokens", headers={"X-API-Key": new_key}).status_code == 200
    assert client.delete(f"/api/admin/api-keys/{new_key}", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/tokens", headers={"X-API-Key": new_key}).status_code == 403
    assert client.delete(f"/api/admin/api-keys/{new_key}", headers=admin_headers).status_code == 404


def test_custom_admin_key_is_kept_verbatim(client, admin_headers):
    """Previously a custom key not starting with the prefix was silently replaced."""
    resp = client.post("/api/admin/api-keys", headers=admin_headers, json={"api_key": "my-custom-key-1234567"})
    assert resp.get_json()["api_key"] == "my-custom-key-1234567"


@pytest.mark.parametrize("body", [{"api_key": "short"}, {"api_key": 123}, {"api_key": "has space in it 12345"}])
def test_custom_admin_key_validation(client, admin_headers, body):
    assert client.post("/api/admin/api-keys", headers=admin_headers, json=body).status_code == 400


def test_config_admin_key_cannot_be_deleted(client, admin_headers):
    assert client.delete(f"/api/admin/api-keys/{ADMIN_KEY}", headers=admin_headers).status_code == 409


def test_admin_never_writes_config(client, admin_headers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client.post("/api/admin/api-keys", headers=admin_headers)
    assert list(tmp_path.iterdir()) == []


def test_tokens_list_and_clear(client, admin_headers):
    client.post("/api/auth/api-key")
    client.post("/api/auth/oauth-token")
    tokens = client.get("/api/admin/tokens", headers=admin_headers).get_json()
    assert tokens["total"] == 3
    assert {t["kind"] for t in tokens["tokens"]} == {"api_key", "oauth_access", "oauth_refresh"}
    assert client.delete("/api/admin/tokens", headers=admin_headers).get_json()["cleared"] == 3
    assert client.get("/api/admin/tokens", headers=admin_headers).get_json()["total"] == 0
