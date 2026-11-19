import json

import pytest

from mockbox.__main__ import main
from mockbox.config import ConfigError, load_settings
from mockbox.features import ALL, FEATURES, FeatureError, feature_for_path, parse_features

from test_openapi import _routes


@pytest.mark.parametrize(
    "value,expected",
    [
        ("all", ALL),
        ("payments", ("payments",)),
        ("store, DATA", ("data", "store")),
        ("-payments,-admin", tuple(f for f in ALL if f not in ("payments", "admin"))),
        ("all,-docs", tuple(f for f in ALL if f != "docs")),
        ("data,-data", ()),
    ],
)
def test_parse_features(value, expected):
    assert parse_features(value) == expected


@pytest.mark.parametrize("value", ["", "paymnts", "-nope"])
def test_parse_features_rejects(value):
    with pytest.raises(FeatureError):
        parse_features(value)


def test_feature_for_path():
    assert feature_for_path("/api/payments/{payment_id}") == "payments"
    assert feature_for_path("/api/store") == "store"
    assert feature_for_path("/api/users") == "data"
    assert feature_for_path("/api/mocks") is None
    assert feature_for_path("/health") is None


COMBINATIONS = [(f,) for f in ALL] + [tuple(x for x in ALL if x != f) for f in ALL] + [()]


@pytest.mark.parametrize("features", COMBINATIONS, ids=lambda f: ",".join(f) or "none")
def test_spec_matches_routes_for_every_combination(make_app, features):
    app = make_app(features=features)
    spec = app.test_client().get("/openapi.json").get_json()
    routes = {(p, m) for p, m, _ in _routes(app)}
    documented = {(p, m) for p, ops in spec["paths"].items() for m in ops}
    assert routes == documented
    used_tags = {op["tags"][0] for ops in spec["paths"].values() for op in ops.values()}
    assert {t["name"] for t in spec["tags"]} == used_tags


def test_only_payments(make_app):
    client = make_app(features=("payments",)).test_client()
    assert client.get("/api/users").status_code == 404
    assert client.get("/api/auth/verify").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/inspect").status_code == 404
    assert client.get("/api/payments").status_code == 200
    assert client.get("/health").get_json()["features"] == {f: f == "payments" for f in FEATURES}
    home = client.get("/").get_json()
    assert home["features"] == ["payments"] and home["openapi"] == "/openapi.json"


def test_disabled_inspector_records_nothing(make_app):
    client = make_app(features=("data", "inspector")).test_client()
    client.get("/api/users")
    assert len(client.get("/api/inspector/requests").get_json()["requests"]) == 1
    assert "mockbox.inspector" not in make_app(features=("data",)).extensions


def test_custom_routes_work_with_no_features(make_app, tmp_path):
    mocks = tmp_path / "m.json"
    mocks.write_text('[{"path": "/hello", "body": {"hi": true}}]', encoding="utf-8")
    client = make_app(features=(), mocks_files=(str(mocks),)).test_client()
    assert client.get("/hello").get_json() == {"hi": True}
    assert "/hello" in client.get("/openapi.json").get_json()["paths"]


def test_features_from_config_and_env(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[server]\nfeatures = data, store\n", encoding="utf-8")
    assert load_settings(str(path), env={}).features == ("data", "store")
    assert load_settings(str(path), env={"MOCKBOX_FEATURES": "-docs"}).features == tuple(f for f in ALL if f != "docs")
    with pytest.raises(ConfigError, match="MOCKBOX_FEATURES"):
        load_settings(str(path), env={"MOCKBOX_FEATURES": "bogus"})


def test_cli_features(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    served = {}
    monkeypatch.setattr("mockbox.__main__.serve", lambda app, *a: served.setdefault("app", app))
    assert main(["--features", "store"]) == 0
    assert served["app"].config["MOCKBOX_SETTINGS"].features == ("store",)
    assert main(["--features", "nope"]) == 2
    assert "--features" in capsys.readouterr().err


def test_cli_prints_openapi(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["--openapi", "--features", "payments"]) == 0
    spec = json.loads(capsys.readouterr().out)
    assert spec["openapi"].startswith("3.") and "/api/payments" in spec["paths"] and "/api/users" not in spec["paths"]
