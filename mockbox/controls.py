"""Query-string controls shared by every mock data endpoint.

* ``?count=N``   -- number of items to generate (1..MAX_COUNT)
* ``?seed=S``    -- make the response reproducible (same seed -> same body)
* ``?delay=MS``  -- wait MS milliseconds before responding (0..MAX_DELAY_MS)
* ``?status=C``  -- skip the endpoint and return an error with status C (400..599)
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Optional

from flask import g, request

from .errors import ApiError, error_response

MAX_COUNT = 1000
MAX_DELAY_MS = 10_000
MAX_SEED_LENGTH = 64
# Seeded responses use a fixed reference time so timestamps are reproducible too.
SEEDED_REFERENCE_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


def int_arg(name: str, default: Optional[int], low: int, high: int) -> Optional[int]:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, f"Query parameter '{name}' must be an integer, got {raw!r}") from None
    if not low <= value <= high:
        raise ApiError(400, f"Query parameter '{name}' must be between {low} and {high}, got {value}")
    return value


def count_arg(default: int) -> int:
    return int_arg("count", default, 1, MAX_COUNT)


def rng() -> random.Random:
    if "mock_rng" not in g:
        g.mock_rng = random.Random()
    return g.mock_rng


def now() -> datetime:
    return g.get("mock_now") or datetime.now(timezone.utc).replace(microsecond=0)


def apply_controls():
    """``before_request`` hook for mock data blueprints."""
    if request.method == "OPTIONS":
        return None  # never delay or fail CORS preflights
    seed = request.args.get("seed")
    if seed is not None:
        if not seed or len(seed) > MAX_SEED_LENGTH:
            raise ApiError(400, f"Query parameter 'seed' must be 1..{MAX_SEED_LENGTH} characters")
        g.mock_rng = random.Random(seed)
        g.mock_now = SEEDED_REFERENCE_TIME
    else:
        g.mock_rng = random.Random()
        g.mock_now = datetime.now(timezone.utc).replace(microsecond=0)

    delay = int_arg("delay", 0, 0, MAX_DELAY_MS)
    status = int_arg("status", None, 400, 599)
    if delay:
        time.sleep(delay / 1000)
    if status is not None:
        return error_response(status, f"Simulated {status} response (requested via ?status={status})")
    return None
