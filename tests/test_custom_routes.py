import json
import os
import time
from pathlib import Path

import pytest

from mockbox import create_app
from mockbox.__main__ import main
from mockbox.config import ConfigError, Settings
from mockbox.custom_routes import MockFileError, load_routes

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def app_with(tmp_path, routes, name="mocks.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"routes": routes}), encoding="utf-8")
    app = create_app(Settings(secret_key="k" * 40, mocks_files=(str(path),)))
    return app.test_client(), path


# --------------------------------------------------------------------------- examples
def test_examples_load():
    routes = load_routes([EXAMPLES / "mocks.yaml", EXAMPLES / "mocks.json"])
    assert len(routes) == 11


@pytest.fixture
def example_client():
    app = create_app(Settings(secret_key="k" * 40, mocks_files=(str(EXAMPLES / "mocks.yaml"),)))
    return app.test_client()


def test_example_path_params_and_types(example_client):
    body = example_client.get("/v1/customers/42").get_json()
    assert body["id"] == "42"
    assert isinstance(body["age"], int) and 18 <= body["age"] <= 80
    assert isinstance(body["verified"], bool)
    first = body["name"].split()[0]
    assert body["greeting"] == f"Hello {first}, your id is 42"
    assert body["email"].startswith(first.lower() + ".")


def test_example_repeat_with_default_and_query(example_client):
    assert len(example_client.get("/v1/customers").get_json()["data"]) == 3
    data = example_client.get("/v1/customers?limit=5").get_json()["data"]
    assert [d["id"] for d in data] == [1, 2, 3, 4, 5]
    assert len({d["name"] for d in data}) > 1


def test_example_seed_is_reproducible(example_client):
    a = example_client.get("/v1/customers?limit=4&seed=s").get_json()
    b = example_client.get("/v1/customers?limit=4&seed=s").get_json()
    assert a == b


def test_example_post_echoes_body(example_client):
    resp = example_client.post("/v1/customers", json={"name": "Jane"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Jane" and body["email"] == "unknown@example.com"
    assert resp.headers["Location"].startswith("/v1/customers/")


@pytest.mark.parametrize(
    "payload,status",
    [({"username": "admin", "password": "secret"}, 200), ({"username": "bob"}, 401), ({}, 400)],
)
def test_example_conditional_responses(example_client, payload, status):
    assert example_client.post("/v1/login", json=payload).status_code == status


def test_example_sequence(example_client):
    statuses = [example_client.get("/v1/flaky").status_code for _ in range(4)]
    assert statuses == [503, 503, 200, 503]


def test_example_auth(example_client):
    assert example_client.get("/v1/me").status_code == 401
    token = example_client.post("/api/auth/jwt-token").get_json()["access_token"]
    assert example_client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_example_body_file(example_client):
    resp = example_client.get("/v1/reports/latest")
    assert resp.content_type == "text/csv" and resp.data.startswith(b"date,orders")


def test_example_overrides_builtin(example_client):
    assert example_client.get("/api/products").get_json()[0]["name"] == "Custom product"
    assert example_client.post("/api/products").status_code == 405  # only GET was overridden


# --------------------------------------------------------------------------- behaviour
def test_unmatched_method_falls_through(tmp_path):
    client, _ = app_with(tmp_path, [{"method": "POST", "path": "/x", "body": {"a": 1}}])
    assert client.post("/x").status_code == 200
    assert client.get("/x").status_code == 404


def test_any_method_and_head(tmp_path):
    client, _ = app_with(tmp_path, [{"method": "ANY", "path": "/any", "body": {"ok": True}}])
    for method in ("get", "post", "put", "patch", "delete", "head"):
        assert getattr(client, method)("/any").status_code == 200


def test_trailing_slash_and_text_body(tmp_path):
    client, _ = app_with(tmp_path, [{"path": "/plain/", "body": "hi {{query.who | there}}"}])
    resp = client.get("/plain?who=you")
    assert resp.data == b"hi you" and resp.mimetype == "text/plain"
    assert client.get("/plain/").data == b"hi there"


def test_empty_body_and_custom_content_type(tmp_path):
    client, _ = app_with(tmp_path, [
        {"path": "/empty", "status": 204},
        {"path": "/xml", "body": "<a>{{params.x | 1}}</a>", "content_type": "application/xml"},
    ])
    assert client.get("/empty").status_code == 204
    resp = client.get("/xml")
    assert resp.mimetype == "application/xml" and resp.data == b"<a>1</a>"


def test_controls_apply_to_custom_routes(tmp_path):
    client, _ = app_with(tmp_path, [{"path": "/c", "body": {"a": 1}}])
    assert client.get("/c?status=418").status_code == 418


def test_when_matches_headers_query_params_and_lists(tmp_path):
    client, _ = app_with(tmp_path, [{
        "path": "/w/{kind}",
        "responses": [
            {"when": {"headers": {"x-tenant": "acme"}}, "body": "header"},
            {"when": {"query": {"v": ["1", "2"]}}, "body": "query"},
            {"when": {"params": {"kind": "special"}}, "body": "param"},
        ],
        "body": "default",
    }])
    assert client.get("/w/a", headers={"X-Tenant": "acme"}).data == b"header"
    assert client.get("/w/a?v=2").data == b"query"
    assert client.get("/w/special").data == b"param"
    assert client.get("/w/a?v=3").data == b"default"


def test_when_body_types(tmp_path):
    client, _ = app_with(tmp_path, [{
        "method": "POST",
        "path": "/b",
        "responses": [{"when": {"body": {"order.qty": 2, "order.gift": True}}, "body": "match"}],
        "body": "no",
    }])
    assert client.post("/b", json={"order": {"qty": 2, "gift": True}}).data == b"match"
    assert client.post("/b", json={"order": {"qty": 3, "gift": True}}).data == b"no"


def test_cors_preflight_on_custom_route(tmp_path):
    client, _ = app_with(tmp_path, [{"method": "POST", "path": "/p", "body": {}}])
    resp = client.options("/p", headers={"Origin": "http://x.test", "Access-Control-Request-Method": "POST"})
    assert resp.status_code == 204 and resp.headers["Access-Control-Allow-Origin"] == "*"


def test_custom_routes_recorded_by_inspector(tmp_path):
    client, _ = app_with(tmp_path, [{"path": "/v9/thing", "body": {}}])
    client.get("/v9/thing")
    paths = [e["path"] for e in client.get("/api/inspector/requests").get_json()["requests"]]
    assert paths == ["/v9/thing"]


def test_custom_routes_in_openapi_and_status(tmp_path):
    client, _ = app_with(tmp_path, [{"path": "/v1/items/{id}", "description": "An item", "auth": "api_key", "body": {}}])
    spec = client.get("/openapi.json").get_json()
    op = spec["paths"]["/v1/items/{id}"]["get"]
    assert op["summary"] == "An item" and op["tags"] == ["Custom"] and op["security"] == [{"ApiKeyAuth": []}]
    status = client.get("/api/mocks").get_json()
    assert status["error"] is None and status["routes"][0]["path"] == "/v1/items/{id}"
    assert b"/v1/items/{id}" in client.get("/").data


def test_hot_reload_and_bad_edit_keeps_previous(tmp_path, monkeypatch):
    monkeypatch.setattr("mockbox.custom_routes.RELOAD_INTERVAL", 0)
    client, path = app_with(tmp_path, [{"path": "/r", "body": {"v": 1}}])
    assert client.get("/r").get_json() == {"v": 1}

    def rewrite(text):
        path.write_text(text, encoding="utf-8")
        stamp = time.time() + 5
        os.utime(path, (stamp, stamp))  # guarantee a new mtime even on coarse filesystems

    rewrite(json.dumps({"routes": [{"path": "/r", "body": {"v": 2}}]}))
    assert client.get("/r").get_json() == {"v": 2}

    rewrite("{ not json")
    assert client.get("/r").get_json() == {"v": 2}
    assert "invalid JSON" in client.get("/api/mocks").get_json()["error"]


def test_no_custom_routes_configured(client):
    assert client.get("/api/mocks").get_json() == {"files": [], "loaded_at": None, "error": None, "routes": []}


# --------------------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "route,message",
    [
        ({"body": {}}, "path is required"),
        ({"path": "no-slash"}, "starting with '/'"),
        ({"path": "/x/{bad-name}"}, "path parameters"),
        ({"path": "/x", "status": 99}, "status"),
        ({"path": "/x", "method": "FETCH"}, "unsupported method"),
        ({"path": "/x", "delay_ms": 999999}, "delay_ms"),
        ({"path": "/x", "auth": "magic"}, "auth"),
        ({"path": "/x", "mode": "random"}, "mode"),
        ({"path": "/x", "mode": "sequence"}, "non-empty responses"),
        ({"path": "/x", "bodyy": {}}, "unknown key"),
        ({"path": "/x", "body": "{{nope}}"}, "Unknown placeholder"),
        ({"path": "/x", "body": {"$repeat": 2}}, "$repeat"),
        ({"path": "/x", "body": {}, "body_file": "a.json"}, "either body or body_file"),
        ({"path": "/x", "body_file": "missing.json"}, "body_file not found"),
        ({"path": "/x", "responses": [{"when": {"cookies": {"a": 1}}}]}, "unknown key"),
    ],
)
def test_validation_errors(tmp_path, route, message):
    path = tmp_path / "m.json"
    path.write_text(json.dumps([route]), encoding="utf-8")
    with pytest.raises(MockFileError, match=message.replace("$", r"\$").replace("{", r"\{").replace("(", r"\(")):
        load_routes([path])


def test_errors_name_the_route(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps([{"path": "/ok"}, {"path": "/bad", "status": "x"}]), encoding="utf-8")
    with pytest.raises(MockFileError, match=r"m\.json: routes\[1\]"):
        load_routes([path])


def test_invalid_file_at_startup_is_config_error(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("[", encoding="utf-8")
    with pytest.raises(ConfigError):
        create_app(Settings(secret_key="k" * 40, mocks_files=(str(path),)))


def test_cli_reports_bad_mocks(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "m.json").write_text("[{}]", encoding="utf-8")
    assert main(["--mocks", "m.json"]) == 2
    assert "path is required" in capsys.readouterr().err


def test_cli_loads_mocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "m.json").write_text('[{"path": "/hi", "body": "hi"}]', encoding="utf-8")
    served = {}
    monkeypatch.setattr("mockbox.__main__.serve", lambda app, *a: served.setdefault("app", app))
    assert main(["--mocks", "m.json"]) == 0
    assert served["app"].test_client().get("/hi").data == b"hi"


def test_yaml_requires_pyyaml(tmp_path, monkeypatch):
    import sys

    path = tmp_path / "m.yaml"
    path.write_text("- path: /x\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(MockFileError, match="mock-box\\[yaml\\]"):
        load_routes([path])
