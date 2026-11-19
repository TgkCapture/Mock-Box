import pytest

from mockbox.store import MAX_ITEMS_PER_COLLECTION, Store


def test_list_collections(client):
    names = {c["name"]: c["count"] for c in client.get("/api/store").get_json()["collections"]}
    assert names == {"users": 10, "products": 20, "orders": 30, "posts": 20, "comments": 50, "todos": 40}


def test_seed_is_deterministic(make_app):
    a = make_app().test_client().get("/api/store/products").get_json()
    b = make_app().test_client().get("/api/store/products").get_json()
    assert [(p["name"], p["price"]) for p in a] == [(p["name"], p["price"]) for p in b]


def test_crud_lifecycle(client):
    created = client.post("/api/store/products", json={"name": "Widget", "price": 9.99})
    assert created.status_code == 201
    item = created.get_json()
    assert item["id"] == 21 and item["name"] == "Widget" and "created_at" in item
    assert created.headers["Location"].endswith("/api/store/products/21")

    assert client.get("/api/store/products/21").get_json()["price"] == 9.99

    patched = client.patch("/api/store/products/21", json={"price": 12.5}).get_json()
    assert patched["price"] == 12.5 and patched["name"] == "Widget" and "updated_at" in patched

    replaced = client.put("/api/store/products/21", json={"name": "Gadget"}).get_json()
    assert replaced["name"] == "Gadget" and "price" not in replaced
    assert replaced["created_at"] == item["created_at"]

    assert client.delete("/api/store/products/21").status_code == 204
    assert client.get("/api/store/products/21").status_code == 404


def test_state_persists_across_requests(client):
    client.post("/api/store/todos", json={"title": "write docs", "completed": False})
    todos = client.get("/api/store/todos?filter[title]=write docs").get_json()
    assert len(todos) == 1


def test_new_collection_on_first_post(client):
    resp = client.post("/api/store/invoices", json={"amount": 100, "currency": "MWK"})
    assert resp.status_code == 201 and resp.get_json()["id"] == 1
    assert client.post("/api/store/invoices", json={"amount": 5}).get_json()["id"] == 2
    assert client.get("/api/store/invoices").get_json()[0]["currency"] == "MWK"


def test_client_supplied_ids(client):
    assert client.post("/api/store/things", json={"id": "abc", "x": 1}).status_code == 201
    assert client.get("/api/store/things/abc").get_json()["x"] == 1
    assert client.post("/api/store/things", json={"id": "abc"}).status_code == 409
    assert client.post("/api/store/things", json={"id": 50}).status_code == 201
    assert client.post("/api/store/things", json={}).status_code == 400
    assert client.post("/api/store/things", json={"x": 2}).get_json()["id"] == 51


@pytest.mark.parametrize("bad_id", [True, 1.5, "", None, [1]])
def test_invalid_ids(client, bad_id):
    assert client.post("/api/store/things", json={"id": bad_id}).status_code == 400


def test_id_cannot_change(client):
    assert client.patch("/api/store/users/1", json={"id": 2}).status_code == 400
    assert client.put("/api/store/users/1", json={"id": 1, "name": "Same id ok"}).status_code == 200


@pytest.mark.parametrize("name", ["Bad", "has space", "x" * 51, "1abc"])
def test_invalid_collection_names(client, name):
    assert client.post(f"/api/store/{name}", json={"a": 1}).status_code in (400, 404, 405)


def test_bodies_must_be_objects(client):
    assert client.post("/api/store/users", json=[1, 2]).status_code == 400
    assert client.patch("/api/store/users/1", data="nope", content_type="application/json").status_code == 400


def test_unknown_collection_and_item(client):
    assert client.get("/api/store/nope").status_code == 404
    assert client.get("/api/store/users/999").status_code == 404
    assert client.put("/api/store/users/999", json={"a": 1}).status_code == 404
    assert client.delete("/api/store/users/999").status_code == 404


def test_listing_features_on_store(client):
    resp = client.get("/api/store/posts?page=1&per_page=5&sort=-id&filter[published]=true")
    rows = resp.get_json()
    assert len(rows) <= 5 and all(r["published"] for r in rows)
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    assert resp.headers["X-Total-Count"]


def test_listing_tolerates_mixed_fields(client):
    client.post("/api/store/mixed", json={"a": 1})
    client.post("/api/store/mixed", json={"b": "x"})
    client.post("/api/store/mixed", json={"a": "text"})
    assert client.get("/api/store/mixed?sort=a").status_code == 200
    assert len(client.get("/api/store/mixed?filter[a]=1").get_json()) == 1
    assert len(client.get("/api/store/mixed?filter[b][contains]=x").get_json()) == 1


def test_drop_and_reset(client):
    client.post("/api/store/invoices", json={"a": 1})
    client.delete("/api/store/users/1")
    assert client.delete("/api/store/products").get_json()["items_removed"] == 20
    assert client.get("/api/store/products").status_code == 404

    body = client.post("/api/store/reset").get_json()
    assert "invoices" not in body["collections"] and body["collections"]["products"] == 20
    assert client.get("/api/store/users/1").status_code == 200


def test_store_supports_controls(client):
    assert client.get("/api/store/users?status=500").status_code == 500


def test_returned_items_are_copies():
    store = Store()
    item = store.get("users", "1")
    item["name"] = "mutated"
    assert store.get("users", "1")["name"] != "mutated"


def test_collection_limit():
    store = Store(seed=lambda: {"full": [{"id": i} for i in range(1, MAX_ITEMS_PER_COLLECTION + 1)]})
    with pytest.raises(Exception) as exc:
        store.create("full", {"x": 1})
    assert exc.value.status == 507


@pytest.mark.parametrize("path", ["/api/posts", "/api/comments", "/api/todos"])
def test_generated_content_endpoints(client, path):
    assert len(client.get(path).get_json()) == 10
    assert len(client.get(f"{path}?page=2&per_page=5").get_json()) == 5


def test_reset_is_not_a_collection_name():
    store = Store()
    with pytest.raises(Exception) as exc:
        store.create("reset", {"x": 1})
    assert exc.value.status == 400
