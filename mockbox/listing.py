"""Pagination, sorting, filtering and search for list endpoints.

Without any of these parameters a list endpoint behaves as before (a bare JSON array of
``count`` items). With them:

* ``?page=2&per_page=10``     page-based pagination (``Link`` / ``X-Total-Count`` headers)
* ``?limit=10&cursor=...``    cursor-based pagination (``X-Next-Cursor`` header)
* ``?sort=-price,name``       sort by one or more fields; ``-`` for descending
* ``?filter[status]=active,overdue``      exact match (comma = any of)
* ``?filter[price][gte]=100``             operators: eq, ne, gt, gte, lt, lte, contains
* ``?q=alice``                case-insensitive search across text fields
* ``?envelope=true``          wrap as ``{"data", "meta", "links"}`` instead of a bare array

Paginated collections are stable between requests (same items on every page load), so
pages never overlap. ``count`` sets the collection size (default 100 when paginating).
"""

from __future__ import annotations

import base64
import binascii
import math
import random
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from flask import g, jsonify, request

from .controls import count_arg, int_arg
from .errors import ApiError

DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100
PAGINATED_DEFAULT_COUNT = 100
MAX_PAGE = 1_000_000

FILTER_RE = re.compile(r"^filter\[([A-Za-z_][A-Za-z0-9_]*)\](?:\[(eq|ne|gt|gte|lt|lte|contains)\])?$")
PAGINATION_HEADERS = ("Link", "X-Total-Count", "X-Page", "X-Per-Page", "X-Total-Pages", "X-Next-Cursor")

Item = Dict[str, Any]


# --------------------------------------------------------------------------- helpers
def _truthy(name: str) -> bool:
    value = request.args.get(name, "").lower()
    if value in ("", "0", "false", "no"):
        return False
    if value in ("1", "true", "yes"):
        return True
    raise ApiError(400, f"Query parameter '{name}' must be true or false")


def _mode() -> Optional[str]:
    args = request.args
    page_mode = "page" in args or "per_page" in args
    cursor_mode = "cursor" in args or "limit" in args
    if page_mode and cursor_mode:
        raise ApiError(400, "Use either page/per_page or cursor/limit, not both")
    return "page" if page_mode else "cursor" if cursor_mode else None


def _stabilize() -> None:
    """Make an unseeded paginated collection identical across requests (pages must not overlap)."""
    if "seed" in request.args:
        return
    g.mock_rng = random.Random(f"mockbox:{request.path}")
    g.mock_now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _coerce(raw: str, sample: Any, field: str) -> Any:
    if isinstance(sample, bool):
        if raw.lower() in ("true", "1"):
            return True
        if raw.lower() in ("false", "0"):
            return False
        raise ApiError(400, f"filter[{field}] expects true or false, got {raw!r}")
    if isinstance(sample, (int, float)):
        for cast in ((int, float) if isinstance(sample, int) else (float,)):
            try:
                return cast(raw)
            except ValueError:
                continue
        raise ApiError(400, f"filter[{field}] expects a number, got {raw!r}")
    return raw


def _matches(value: Any, op: str, target: Any) -> bool:
    if op == "contains":
        return str(target).lower() in str(value).lower()
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    try:
        return {"gt": value > target, "gte": value >= target, "lt": value < target, "lte": value <= target}[op]
    except TypeError:
        return False


def apply_filters(items: List[Item]) -> List[Item]:
    sample = items[0] if items else {}
    for key in request.args:
        if not key.startswith("filter["):
            continue
        match = FILTER_RE.match(key)
        if not match:
            raise ApiError(400, f"Malformed filter parameter {key!r}; use filter[field] or filter[field][op]")
        field, op = match.group(1), match.group(2) or "eq"
        if sample and field not in sample:
            raise ApiError(400, f"Cannot filter on unknown field {field!r}; fields: {', '.join(sample)}")
        raw = request.args.get(key, "")
        if op in ("eq", "ne"):
            targets = [_coerce(v.strip(), sample.get(field), field) for v in raw.split(",")]
            if op == "eq":
                items = [i for i in items if i[field] in targets]
            else:
                items = [i for i in items if i[field] not in targets]
        else:
            target = raw if op == "contains" else _coerce(raw, sample.get(field), field)
            items = [i for i in items if _matches(i[field], op, target)]

    query = request.args.get("q", "").strip().lower()
    if query:
        items = [i for i in items if any(isinstance(v, str) and query in v.lower() for v in i.values())]
    return items


def apply_sort(items: List[Item]) -> List[Item]:
    spec = request.args.get("sort", "").strip()
    if not spec or not items:
        return items
    fields: List[Tuple[str, bool]] = []
    for part in spec.split(","):
        part = part.strip()
        desc = part.startswith("-")
        name = part.lstrip("-+")
        if name not in items[0]:
            raise ApiError(400, f"Cannot sort on unknown field {name!r}; fields: {', '.join(items[0])}")
        fields.append((name, desc))
    for name, desc in reversed(fields):  # stable multi-key sort
        items = sorted(items, key=lambda i: i[name], reverse=desc)
    return items


def _url(**params: Any) -> str:
    args = request.args.to_dict(flat=False)
    for key, value in params.items():
        if value is None:
            args.pop(key, None)
        else:
            args[key] = [str(value)]
    return f"{request.base_url}?{urlencode(args, doseq=True)}"


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        prefix, _, offset = raw.partition(":")
        if prefix != "o" or not offset.isdigit():
            raise ValueError
        return int(offset)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise ApiError(400, "Invalid cursor") from None


# --------------------------------------------------------------------------- entry point
def list_response(generate: Callable[[int], List[Item]], default_count: int):
    """Build the response for a list endpoint. ``generate(n)`` returns ``n`` items."""
    mode = _mode()
    envelope = _truthy("envelope")
    if mode:
        _stabilize()
    count = count_arg(PAGINATED_DEFAULT_COUNT if mode else default_count)
    items = apply_sort(apply_filters(generate(count)))
    total = len(items)

    if mode is None:
        if envelope:
            return jsonify({"data": items, "meta": {"total": total}})
        return jsonify(items)

    headers: Dict[str, str] = {"X-Total-Count": str(total)}
    links: Dict[str, Optional[str]] = {}

    if mode == "page":
        page = int_arg("page", 1, 1, MAX_PAGE)
        per_page = int_arg("per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
        total_pages = max(1, math.ceil(total / per_page))
        data = items[(page - 1) * per_page : page * per_page]
        links = {
            "self": _url(page=page, per_page=per_page),
            "first": _url(page=1, per_page=per_page),
            "prev": _url(page=page - 1, per_page=per_page) if 1 < page <= total_pages + 1 else None,
            "next": _url(page=page + 1, per_page=per_page) if page < total_pages else None,
            "last": _url(page=total_pages, per_page=per_page),
        }
        meta = {"total": total, "page": page, "per_page": per_page, "total_pages": total_pages}
        headers.update({"X-Page": str(page), "X-Per-Page": str(per_page), "X-Total-Pages": str(total_pages)})
    else:
        limit = int_arg("limit", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
        cursor = request.args.get("cursor")
        offset = decode_cursor(cursor) if cursor else 0
        data = items[offset : offset + limit]
        next_offset = offset + limit
        next_cursor = encode_cursor(next_offset) if next_offset < total else None
        links = {"self": _url(cursor=cursor, limit=limit), "next": _url(cursor=next_cursor, limit=limit) if next_cursor else None}
        meta = {"total": total, "limit": limit, "next_cursor": next_cursor, "has_more": next_cursor is not None}
        if next_cursor:
            headers["X-Next-Cursor"] = next_cursor

    link_header = ", ".join(f'<{url}>; rel="{rel}"' for rel, url in links.items() if url and rel != "self")
    if link_header:
        headers["Link"] = link_header

    body = {"data": data, "meta": meta, "links": links} if envelope else data
    return jsonify(body), 200, headers
