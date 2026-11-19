"""Pure mock-data generators.

Every generator takes a ``random.Random`` and a reference ``now`` so callers control
reproducibility. Add new generators here and expose them from a route module.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from email.utils import format_datetime
from typing import Any, Dict, List

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank", "Ivy", "Jack",
    "Kondwani", "Chikondi", "Thandiwe", "Mphatso", "Tiyamike", "Lena", "Omar", "Priya", "Sven", "Yuki",
]
LAST_NAMES = [
    "Banda", "Phiri", "Mwale", "Chirwa", "Smith", "Johnson", "Garcia", "Kim", "Nguyen", "Okafor",
    "Mbewe", "Kumwenda", "Silva", "Novak", "Schmidt", "Rossi", "Dubois", "Tanaka", "Patel", "Cohen",
]
PRODUCT_CATALOG = [
    ("Laptop", "computers", 500, 1500),
    ("Smartphone", "phones", 200, 800),
    ("Headphones", "audio", 50, 300),
    ("Monitor", "computers", 100, 400),
    ("Keyboard", "accessories", 20, 100),
    ("Mouse", "accessories", 10, 60),
    ("Tablet", "computers", 150, 700),
    ("Smartwatch", "wearables", 80, 400),
    ("Speaker", "audio", 30, 250),
    ("Webcam", "accessories", 25, 120),
]
ORDER_STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]
ACTIVITY_TYPES = ["login", "logout", "purchase", "viewed_product", "added_to_cart"]
CREDIT_LINE_STATUSES = ["active", "inactive", "overdue"]
# Malawi mobile format: +265 88x xxx xxx (TNM).
PHONE_PREFIX = "+26588"


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _money(value: float) -> float:
    return round(value, 2)


def _person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def product_name(product_id: int) -> str:
    """Stable name for a product id, shared by /products and /orders."""
    name = PRODUCT_CATALOG[(product_id - 1) % len(PRODUCT_CATALOG)][0]
    series = (product_id - 1) // len(PRODUCT_CATALOG)
    return name if series == 0 else f"{name} Mk{series + 1}"


def phone_numbers(rng: random.Random, count: int) -> List[str]:
    return [f"{PHONE_PREFIX}{rng.randrange(10**7):07d}" for _ in range(count)]


def names(rng: random.Random, count: int) -> List[Dict[str, Any]]:
    return [{"id": i, "name": _person(rng)} for i in range(1, count + 1)]


def users(rng: random.Random, now: datetime, count: int) -> List[Dict[str, Any]]:
    result = []
    for i in range(1, count + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        result.append({
            "id": i,
            "name": f"{first} {last}",
            "email": f"{first}.{last}{i}@example.com".lower(),
            "phone": phone_numbers(rng, 1)[0],
            "joined_date": iso(now - timedelta(days=rng.randint(1, 1000), seconds=rng.randrange(86400))),
        })
    return result


def products(rng: random.Random, count: int) -> List[Dict[str, Any]]:
    result = []
    for i in range(1, count + 1):
        _, category, low, high = PRODUCT_CATALOG[(i - 1) % len(PRODUCT_CATALOG)]
        result.append({
            "id": i,
            "name": product_name(i),
            "category": category,
            "price": _money(rng.uniform(low, high)),
            "in_stock": rng.random() < 0.7,
        })
    return result


def orders(rng: random.Random, now: datetime, count: int) -> List[Dict[str, Any]]:
    result = []
    for i in range(1, count + 1):
        product_id = rng.randint(1, len(PRODUCT_CATALOG))
        _, _, low, high = PRODUCT_CATALOG[product_id - 1]
        quantity = rng.randint(1, 5)
        unit_price = _money(rng.uniform(low, high))
        result.append({
            "order_id": 1000 + i,
            "user_id": rng.randint(1, 50),
            "product_id": product_id,
            "product": product_name(product_id),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": _money(unit_price * quantity),
            "status": rng.choice(ORDER_STATUSES),
            "order_date": iso(now - timedelta(days=rng.randint(1, 365), seconds=rng.randrange(86400))),
        })
    return result


def credit_lines(rng: random.Random, count: int) -> List[Dict[str, Any]]:
    result = []
    for i in range(1, count + 1):
        limit = _money(rng.uniform(1000, 10000))
        status = rng.choice(CREDIT_LINE_STATUSES)
        if status == "inactive":
            balance = 0.0
        elif status == "overdue":
            balance = _money(rng.uniform(0.6, 1.1) * limit)
        else:
            balance = _money(rng.uniform(0, limit))
        result.append({
            "credit_line_id": i,
            "customer_name": _person(rng),
            "credit_limit": limit,
            "balance": balance,
            "available_credit": _money(max(limit - balance, 0.0)),
            "status": status,
        })
    return result


def user_activities(rng: random.Random, now: datetime, count: int) -> List[Dict[str, Any]]:
    stamps = sorted((now - timedelta(seconds=rng.randrange(72 * 3600)) for _ in range(count)), reverse=True)
    return [
        {
            "activity_id": i,
            "user_id": rng.randint(1, 100),
            "activity_type": rng.choice(ACTIVITY_TYPES),
            "timestamp": iso(stamp),
        }
        for i, stamp in enumerate(stamps, start=1)
    ]


def rss_items(rng: random.Random, now: datetime, count: int) -> List[Dict[str, Any]]:
    stamps = sorted((now - timedelta(seconds=rng.randrange(30 * 86400)) for _ in range(count)), reverse=True)
    return [
        {
            "title": f"News Item {i}",
            "description": f"This is the description for news item {i}.",
            "link": f"https://example.com/news/{i}",
            "guid": f"https://example.com/news/{i}",
            "pubDate": format_datetime(stamp, usegmt=True),
        }
        for i, stamp in enumerate(stamps, start=1)
    ]


WORDS = (
    "api client mock server request response token data test build deploy cache queue event "
    "user order product payment invoice report update release feature bug fix design review "
    "team project service network mobile money market price stock delivery customer support"
).split()


def _sentence(rng: random.Random, low: int = 5, high: int = 12) -> str:
    words = [rng.choice(WORDS) for _ in range(rng.randint(low, high))]
    return " ".join(words).capitalize() + "."


def _paragraph(rng: random.Random, sentences: int = 3) -> str:
    return " ".join(_sentence(rng) for _ in range(sentences))


def posts(rng: random.Random, now: datetime, count: int, users: int = 10) -> List[Dict[str, Any]]:
    return [
        {
            "id": i,
            "user_id": rng.randint(1, users),
            "title": _sentence(rng, 3, 7).rstrip("."),
            "body": _paragraph(rng, rng.randint(2, 4)),
            "published": rng.random() < 0.8,
            "created_at": iso(now - timedelta(days=rng.randint(0, 365), seconds=rng.randrange(86400))),
        }
        for i in range(1, count + 1)
    ]


def comments(rng: random.Random, count: int, posts: int = 20) -> List[Dict[str, Any]]:
    result = []
    for i in range(1, count + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        result.append({
            "id": i,
            "post_id": rng.randint(1, posts),
            "name": f"{first} {last}",
            "email": f"{first}.{last}@example.com".lower(),
            "body": _sentence(rng, 6, 18),
        })
    return result


def todos(rng: random.Random, count: int, users: int = 10) -> List[Dict[str, Any]]:
    return [
        {"id": i, "user_id": rng.randint(1, users), "title": _sentence(rng, 3, 8).rstrip("."), "completed": rng.random() < 0.4}
        for i in range(1, count + 1)
    ]
