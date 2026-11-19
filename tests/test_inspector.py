import io

import pytest

from mockbox.inspector import Inspector, mask_header


@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
def test_echo_methods(client, method):
    body = getattr(client, method)("/api/echo/some/path?a=1&a=2&b=x", headers={"X-Custom": "hello"}).get_json()
    assert body["method"] == method.upper()
    assert body["path"] == "/api/echo/some/path"
    assert body["query"] == {"a": ["1", "2"], "b": ["x"]}
    assert body["headers"]["X-Custom"] == "hello"


def test_echo_json(client):
    body = client.post("/api/echo", json={"name": "jane", "tags": [1, 2]}).get_json()
    assert body["json"] == {"name": "jane", "tags": [1, 2]}
    assert body["body"] is None


def test_echo_form_and_files(client):
    data = {"title": "hi", "upload": (io.BytesIO(b"hello world"), "hello.txt", "text/plain")}
    body = client.post("/api/echo", data=data, content_type="multipart/form-data").get_json()
    assert body["form"] == {"title": ["hi"]}
    assert body["files"] == [{"field": "upload", "filename": "hello.txt", "content_type": "text/plain", "size": 11}]


def test_echo_raw_text(client):
    body = client.post("/api/echo", data="plain text", content_type="text/plain").get_json()
    assert body["body"] == {"size": 10, "text": "plain text", "truncated": False}


def test_echo_shows_credentials_to_the_caller(client):
    body = client.get("/api/echo", headers={"Authorization": "Bearer my-secret-token-123"}).get_json()
    assert body["headers"]["Authorization"] == "Bearer my-secret-token-123"


def test_echo_supports_controls(client):
    assert client.post("/api/echo?status=502").status_code == 502


def test_request_too_large(client):
    resp = client.post("/api/echo", data=b"x" * (10 * 1024 * 1024 + 1), content_type="application/octet-stream")
    assert resp.status_code == 413
    assert resp.get_json()["error"]["status"] == 413


def test_inspector_records_api_requests(client):
    client.post("/api/echo?x=1", json={"hello": "world"}, headers={"Authorization": "Bearer abcdefghijklmnop"})
    client.get("/api/products?status=503")
    client.get("/health")  # not under /api, not recorded

    entries = client.get("/api/inspector/requests").get_json()["requests"]
    assert [(e["method"], e["path"], e["status"]) for e in entries] == [
        ("GET", "/api/products", 503),
        ("POST", "/api/echo", 200),
    ]
    echo = entries[1]
    assert echo["query"] == "x=1"
    assert echo["request_body"]["text"] == '{"hello": "world"}'
    assert echo["request_headers"]["Authorization"] == "Bearer abcdef...mnop"
    assert echo["duration_ms"] >= 0


def test_inspector_does_not_record_itself(client):
    client.get("/api/inspector/requests")
    assert client.get("/api/inspector/requests").get_json()["total"] == 0


def test_inspector_filters_get_and_clear(client):
    client.get("/api/users")
    client.post("/api/echo")
    only_post = client.get("/api/inspector/requests?method=post").get_json()["requests"]
    assert [e["path"] for e in only_post] == ["/api/echo"]
    only_users = client.get("/api/inspector/requests?path=users").get_json()["requests"]
    assert len(only_users) == 1

    entry_id = only_post[0]["id"]
    assert client.get(f"/api/inspector/requests/{entry_id}").get_json()["path"] == "/api/echo"
    assert client.get("/api/inspector/requests/99999").status_code == 404
    assert client.delete("/api/inspector/requests").get_json()["cleared"] == 2
    assert client.get("/api/inspector/requests").get_json()["total"] == 0


def test_inspector_ring_buffer():
    inspector = Inspector(max_entries=3)
    for i in range(5):
        inspector.record({"method": "GET", "path": f"/api/{i}"})
    assert [e["path"] for e in inspector.list()] == ["/api/4", "/api/3", "/api/2"]


def test_form_parsing_still_works_after_capture(client):
    resp = client.post("/api/auth/oauth-token", data={"grant_type": "client_credentials", "scope": "read"})
    assert resp.get_json()["scope"] == "read"


@pytest.mark.parametrize(
    "name,value,expected",
    [
        ("Authorization", "Bearer abcdefghijklmnop", "Bearer abcdef...mnop"),
        ("Authorization", "Basic short", "Basic ***"),
        ("X-API-Key", "mock_0123456789abcdef", "mock_0...cdef"),
        ("Cookie", "a=b", "***"),
        ("Accept", "application/json", "application/json"),
    ],
)
def test_mask_header(name, value, expected):
    assert mask_header(name, value) == expected


def test_inspect_page(client):
    resp = client.get("/inspect")
    assert resp.status_code == 200 and b"Request inspector" in resp.data
