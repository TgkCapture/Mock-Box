import time
import xml.etree.ElementTree as ET

import pytest

ENDPOINTS = {
    "/api/products": 5,
    "/api/users": 4,
    "/api/orders": 3,
    "/api/credit-lines": 5,
    "/api/user-activities": 10,
    "/api/data?type=numbers": 50,
    "/api/data?type=names": 10,
}


def url(path, **params):
    sep = "&" if "?" in path else "?"
    return path + (sep + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")


@pytest.mark.parametrize("path,default_count", ENDPOINTS.items())
def test_default_counts(client, path, default_count):
    resp = client.get(path)
    assert resp.status_code == 200
    assert len(resp.get_json()) == default_count


@pytest.mark.parametrize("path", ENDPOINTS)
def test_count_param(client, path):
    assert len(client.get(url(path, count=7)).get_json()) == 7


@pytest.mark.parametrize("path", [*ENDPOINTS, "/api/rss-feed", "/api/phone-numbers/public"])
def test_seed_is_fully_reproducible(client, path):
    first = client.get(url(path, seed="abc")).get_data()
    second = client.get(url(path, seed="abc")).get_data()
    other = client.get(url(path, seed="xyz")).get_data()
    assert first == second
    assert first != other


@pytest.mark.parametrize("query", ["count=0", "count=1001", "count=abc", "delay=-1", "delay=10001", "status=200", "status=600"])
def test_invalid_controls_are_400(client, query):
    resp = client.get(f"/api/products?{query}")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["status"] == 400


def test_status_override(client):
    resp = client.get("/api/users?status=429")
    assert resp.status_code == 429
    assert "Simulated 429" in resp.get_json()["error"]["message"]


def test_delay(client):
    start = time.perf_counter()
    assert client.get("/api/products?delay=150").status_code == 200
    assert time.perf_counter() - start >= 0.14


def test_data_names_regression(client):
    """Used to crash with NameError (missing import)."""
    names = client.get("/api/data?type=names&count=3").get_json()
    assert [n["id"] for n in names] == [1, 2, 3]


def test_data_unknown_type(client):
    resp = client.get("/api/data?type=widgets")
    assert resp.status_code == 400
    assert "numbers" in resp.get_json()["error"]["message"]


def test_phone_number_format(client):
    numbers = client.get("/api/phone-numbers/public?count=20").get_json()["phone_numbers"]
    assert all(n.startswith("+26588") and len(n) == 13 and n[1:].isdigit() for n in numbers)


def test_orders_are_internally_consistent(client):
    for order in client.get("/api/orders?count=50").get_json():
        assert order["total_price"] == round(order["unit_price"] * order["quantity"], 2)
        assert order["order_date"].endswith("Z")


def test_credit_lines_are_consistent(client):
    for line in client.get("/api/credit-lines?count=100").get_json():
        assert line["available_credit"] == round(max(line["credit_limit"] - line["balance"], 0), 2)
        if line["status"] == "inactive":
            assert line["balance"] == 0
        if line["status"] == "active":
            assert line["balance"] <= line["credit_limit"]


def test_activities_sorted_newest_first(client):
    stamps = [a["timestamp"] for a in client.get("/api/user-activities?count=30").get_json()]
    assert stamps == sorted(stamps, reverse=True)


def test_rss_json(client):
    channel = client.get("/api/rss-feed?count=2").get_json()["channel"]
    assert len(channel["items"]) == 2
    assert channel["items"][0]["pubDate"].endswith("GMT")


def test_rss_xml_is_valid(client):
    resp = client.get("/api/rss-feed?format=xml&count=3")
    assert resp.mimetype == "application/rss+xml"
    root = ET.fromstring(resp.data)
    assert root.tag == "rss" and len(root.findall("./channel/item")) == 3


def test_rss_bad_format(client):
    assert client.get("/api/rss-feed?format=yaml").status_code == 400


@pytest.mark.parametrize("path,status", [("/api/error", 500), ("/api/error/418", 418), ("/api/error/503", 503), ("/api/error/200", 400)])
def test_error_simulation(client, path, status):
    assert client.get(path).status_code == status


def test_unknown_route_is_json_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["status"] == 404


def test_wrong_method_is_json_405(client):
    resp = client.post("/api/products")
    assert resp.status_code == 405
    assert "GET" in resp.headers["Allow"]


def test_health_and_pages(client):
    assert client.get("/health").get_json()["status"] == "healthy"
    assert b"Mock-Box" in client.get("/").data
    assert b"swagger-ui" in client.get("/docs").data


def test_cors_headers(client):
    resp = client.get("/api/products", headers={"Origin": "http://localhost:3000"})
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_cors_preflight_ignores_controls(client):
    resp = client.options(
        "/api/phone-numbers?status=500&delay=5000",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]


def test_cors_allow_list(make_app):
    client = make_app(cors_origins=("http://allowed.test",)).test_client()
    ok = client.get("/api/products", headers={"Origin": "http://allowed.test"})
    blocked = client.get("/api/products", headers={"Origin": "http://evil.test"})
    assert ok.headers["Access-Control-Allow-Origin"] == "http://allowed.test"
    assert "Access-Control-Allow-Origin" not in blocked.headers
