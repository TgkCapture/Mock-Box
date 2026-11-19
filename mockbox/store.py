"""In-memory, schemaless document store behind /api/store.

Collections are lists of JSON objects keyed by ``id``. Built-in collections are seeded with
generated data; any other collection is created on its first POST. Everything lives in
memory (per process) and ``reset()`` restores the seed data.
"""

from __future__ import annotations

import copy
import random
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import generators

EXTENSION_KEY = "mockbox.store"
COLLECTION_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,49}$")
MAX_COLLECTIONS = 100
MAX_ITEMS_PER_COLLECTION = 10_000
SEED = "mockbox-store"
RESERVED_NAMES = {"reset"}

Item = Dict[str, Any]


class StoreError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _timestamp() -> str:
    return generators.iso(datetime.now(timezone.utc).replace(microsecond=0))


def seed_data() -> Dict[str, List[Item]]:
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "users": generators.users(rng, now, 10),
        "products": generators.products(rng, 20),
        # The store keys everything by "id"; generated orders call it "order_id".
        "orders": [{"id": o.pop("order_id"), **o} for o in generators.orders(rng, now, 30)],
        "posts": generators.posts(rng, now, 20, users=10),
        "comments": generators.comments(rng, 50, posts=20),
        "todos": generators.todos(rng, 40, users=10),
    }


class Store:
    def __init__(self, seed: Callable[[], Dict[str, List[Item]]] = seed_data):
        self._seed = seed
        self._lock = threading.RLock()
        self._collections: Dict[str, Dict[str, Item]] = {}
        self._next_id: Dict[str, int] = {}
        self.reset()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _key(item_id: Any) -> str:
        return str(item_id)

    def _require(self, name: str) -> Dict[str, Item]:
        if name not in self._collections:
            raise StoreError(404, f"Collection {name!r} does not exist")
        return self._collections[name]

    def _bump_next_id(self, name: str, item_id: Any) -> None:
        if isinstance(item_id, int) and not isinstance(item_id, bool):
            self._next_id[name] = max(self._next_id.get(name, 1), item_id + 1)

    # ------------------------------------------------------------------ collections
    def reset(self) -> None:
        with self._lock:
            self._collections = {}
            self._next_id = {}
            for name, items in self._seed().items():
                self._collections[name] = {}
                for item in items:
                    self._collections[name][self._key(item["id"])] = item
                    self._bump_next_id(name, item["id"])

    def collections(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(items) for name, items in self._collections.items()}

    def drop(self, name: str) -> int:
        with self._lock:
            removed = len(self._require(name))
            del self._collections[name]
            self._next_id.pop(name, None)
            return removed

    # ------------------------------------------------------------------ items
    def list(self, name: str) -> List[Item]:
        with self._lock:
            return copy.deepcopy(list(self._require(name).values()))

    def get(self, name: str, item_id: str) -> Item:
        with self._lock:
            item = self._require(name).get(item_id)
            if item is None:
                raise StoreError(404, f"No item with id {item_id!r} in {name!r}")
            return copy.deepcopy(item)

    def create(self, name: str, data: Item) -> Item:
        with self._lock:
            if name not in self._collections:
                if not COLLECTION_NAME_RE.match(name) or name in RESERVED_NAMES:
                    raise StoreError(400, "Collection names must match [a-z][a-z0-9_-]{0,49} and not be 'reset'")
                if len(self._collections) >= MAX_COLLECTIONS:
                    raise StoreError(507, f"Too many collections (max {MAX_COLLECTIONS}); reset or drop some")
                self._collections[name] = {}
            items = self._collections[name]
            if len(items) >= MAX_ITEMS_PER_COLLECTION:
                raise StoreError(507, f"Collection {name!r} is full (max {MAX_ITEMS_PER_COLLECTION} items)")

            item = copy.deepcopy(data)
            if "id" in item:
                if not isinstance(item["id"], (int, str)) or isinstance(item["id"], bool) or item["id"] == "":
                    raise StoreError(400, "id must be a non-empty string or an integer")
                if self._key(item["id"]) in items:
                    raise StoreError(409, f"An item with id {item['id']!r} already exists in {name!r}")
            else:
                item["id"] = self._next_id.get(name, 1)
            self._bump_next_id(name, item["id"])
            item = {"id": item.pop("id"), **item}
            item.setdefault("created_at", _timestamp())
            items[self._key(item["id"])] = item
            return copy.deepcopy(item)

    def replace(self, name: str, item_id: str, data: Item) -> Item:
        with self._lock:
            items = self._require(name)
            current = items.get(item_id)
            if current is None:
                raise StoreError(404, f"No item with id {item_id!r} in {name!r}")
            self._check_id_unchanged(current, data)
            item = {"id": current["id"], **{k: v for k, v in copy.deepcopy(data).items() if k != "id"}}
            if "created_at" in current:
                item.setdefault("created_at", current["created_at"])
            item["updated_at"] = _timestamp()
            items[item_id] = item
            return copy.deepcopy(item)

    def update(self, name: str, item_id: str, data: Item) -> Item:
        with self._lock:
            items = self._require(name)
            current = items.get(item_id)
            if current is None:
                raise StoreError(404, f"No item with id {item_id!r} in {name!r}")
            self._check_id_unchanged(current, data)
            current.update({k: v for k, v in copy.deepcopy(data).items() if k != "id"})
            current["updated_at"] = _timestamp()
            return copy.deepcopy(current)

    def delete(self, name: str, item_id: str) -> None:
        with self._lock:
            items = self._require(name)
            if items.pop(item_id, None) is None:
                raise StoreError(404, f"No item with id {item_id!r} in {name!r}")

    @staticmethod
    def _check_id_unchanged(current: Item, data: Item) -> None:
        if "id" in data and str(data["id"]) != str(current["id"]):
            raise StoreError(400, "The id in the body does not match the URL; ids cannot be changed")


def get_store() -> Store:
    from flask import current_app

    return current_app.extensions[EXTENSION_KEY]
