import pytest

LIST_ENDPOINTS = ["/api/users", "/api/products", "/api/orders", "/api/credit-lines", "/api/user-activities"]
ID_FIELD = {
    "/api/users": "id",
    "/api/products": "id",
    "/api/orders": "order_id",
    "/api/credit-lines": "credit_line_id",
    "/api/user-activities": "activity_id",
}


def test_plain_request_is_unchanged(client):
    resp = client.get("/api/products")
    assert isinstance(resp.get_json(), list) and len(resp.get_json()) == 5
    assert "X-Total-Count" not in resp.headers


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_pages_are_disjoint_and_complete(client, path):
    key = ID_FIELD[path]
    seen = []
    for page in range(1, 5):
        resp = client.get(f"{path}?page={page}&per_page=10&count=35")
        assert resp.status_code == 200
        seen += [item[key] for item in resp.get_json()]
    assert len(seen) == 35 == len(set(seen))


def test_unseeded_pages_are_stable(client):
    first = client.get("/api/users?page=2&per_page=5").get_json()
    again = client.get("/api/users?page=2&per_page=5").get_json()
    assert first == again


def test_page_headers_and_links(client):
    resp = client.get("/api/products?page=2&per_page=10")
    h = resp.headers
    assert (h["X-Total-Count"], h["X-Page"], h["X-Per-Page"], h["X-Total-Pages"]) == ("100", "2", "10", "10")
    for rel in ("first", "prev", "next", "last"):
        assert f'rel="{rel}"' in h["Link"]
    assert "page=3" in h["Link"]


def test_last_page_has_no_next(client):
    link = client.get("/api/products?page=10&per_page=10").headers["Link"]
    assert 'rel="next"' not in link and 'rel="prev"' in link


def test_page_past_end_is_empty(client):
    assert client.get("/api/products?page=99&per_page=10").get_json() == []


def test_envelope(client):
    body = client.get("/api/orders?page=1&per_page=3&count=7&envelope=true").get_json()
    assert len(body["data"]) == 3
    assert body["meta"] == {"total": 7, "page": 1, "per_page": 3, "total_pages": 3}
    assert body["links"]["prev"] is None and "page=2" in body["links"]["next"]


def test_envelope_without_pagination(client):
    body = client.get("/api/users?envelope=1&count=2").get_json()
    assert body["meta"] == {"total": 2} and len(body["data"]) == 2


def test_cursor_pagination_walks_everything(client):
    ids, cursor = [], None
    for _ in range(10):
        url = "/api/users?limit=4&count=10&envelope=true" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url).get_json()
        ids += [u["id"] for u in body["data"]]
        cursor = body["meta"]["next_cursor"]
        if not body["meta"]["has_more"]:
            break
    assert ids == list(range(1, 11))


def test_cursor_header(client):
    resp = client.get("/api/users?limit=2&count=5")
    assert resp.headers["X-Next-Cursor"]
    assert len(resp.get_json()) == 2


@pytest.mark.parametrize(
    "query",
    ["page=1&cursor=abc", "cursor=!!!", "per_page=101", "page=0", "sort=nope", "filter[nope]=1", "filter[price][between]=1", "filter[price]=cheap", "envelope=maybe"],
)
def test_invalid_listing_params(client, query):
    assert client.get(f"/api/products?{query}").status_code == 400


def test_sort_desc_and_multi_key(client):
    prices = [p["price"] for p in client.get("/api/products?count=30&sort=-price").get_json()]
    assert prices == sorted(prices, reverse=True)
    rows = client.get("/api/products?count=30&sort=category,-price").get_json()
    assert rows == sorted(sorted(rows, key=lambda r: r["price"], reverse=True), key=lambda r: r["category"])


def test_filter_exact_any_of(client):
    rows = client.get("/api/credit-lines?count=60&filter[status]=active,overdue").get_json()
    assert rows and {r["status"] for r in rows} <= {"active", "overdue"}


def test_filter_ne_and_numeric_ops(client):
    rows = client.get("/api/products?count=60&filter[price][gte]=100&filter[price][lt]=500&filter[category][ne]=audio").get_json()
    assert rows and all(100 <= r["price"] < 500 and r["category"] != "audio" for r in rows)


def test_filter_bool(client):
    rows = client.get("/api/products?count=40&filter[in_stock]=false").get_json()
    assert rows and not any(r["in_stock"] for r in rows)


def test_filter_contains_and_q(client):
    rows = client.get("/api/users?count=80&filter[email][contains]=BANDA").get_json()
    assert rows and all("banda" in r["email"] for r in rows)
    rows = client.get("/api/users?count=80&q=phiri").get_json()
    assert rows and all("phiri" in (r["name"] + r["email"]).lower() for r in rows)


def test_filter_then_paginate_total(client):
    resp = client.get("/api/credit-lines?count=50&filter[status]=inactive&page=1&per_page=5")
    total = int(resp.headers["X-Total-Count"])
    assert 0 < total < 50
    assert all(r["status"] == "inactive" for r in resp.get_json())


def test_cors_exposes_pagination_headers(client):
    resp = client.get("/api/users?page=1", headers={"Origin": "http://localhost:3000"})
    assert "X-Total-Count" in resp.headers["Access-Control-Expose-Headers"]
