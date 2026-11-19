"""``{{ placeholder }}`` rendering for custom route responses.

Deliberately not a general template language: placeholders are matched against a fixed
grammar (no eval, no attribute access), so a mocks file can never execute code.

Placeholders
------------
Request data:   params.<name>  query.<name>  headers.<name>  body.<dotted.path>
Generated:      uuid  now  date  timestamp  name  first_name  last_name  email  phone
                word  sentence  paragraph  bool  index (inside $repeat)
Random:         random.int(1,100)  random.float(0,1)  random.choice(a,b,c)
Default:        query.page | 1     (used when the value is missing)

A string that is exactly one placeholder keeps the value's type (``"{{random.int(1,9)}}"``
renders as a number); placeholders inside longer strings are interpolated as text.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from random import Random
from typing import Any, Dict, List, Mapping, Optional

from . import generators

PLACEHOLDER_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")
_REQUEST_RE = re.compile(r"^(params|query|headers|body)\.([A-Za-z0-9_.\-]+)$")
_RANDOM_NUM_RE = re.compile(r"^random\.(int|float)\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)$")
_RANDOM_CHOICE_RE = re.compile(r"^random\.choice\((.+)\)$")
SIMPLE = {
    "uuid", "now", "date", "timestamp", "name", "first_name", "last_name", "email", "phone",
    "word", "sentence", "paragraph", "bool", "index",
}
MAX_REPEAT = 1000
MISSING = object()


class TemplateError(ValueError):
    pass


@dataclass
class RenderContext:
    rng: Random
    now: datetime
    params: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: Any = None
    index: Optional[int] = None
    person: Optional[tuple] = None  # shared by name/first_name/last_name/email within one object


def _split_default(expr: str):
    if "|" in expr and not expr.startswith("random.choice("):
        name, default = expr.split("|", 1)
        return name.strip(), default.strip()
    return expr, None


def validate_expression(expr: str) -> None:
    name, _ = _split_default(expr)
    if name in SIMPLE or _REQUEST_RE.match(name) or _RANDOM_NUM_RE.match(name) or _RANDOM_CHOICE_RE.match(name):
        return
    raise TemplateError(f"Unknown placeholder {{{{{expr}}}}}")


def validate(value: Any) -> None:
    """Raise TemplateError for any unknown placeholder or malformed $repeat in ``value``."""
    if isinstance(value, str):
        for match in PLACEHOLDER_RE.finditer(value):
            validate_expression(match.group(1))
    elif isinstance(value, list):
        for item in value:
            validate(item)
    elif isinstance(value, dict):
        if "$repeat" in value:
            extra = set(value) - {"$repeat", "item"}
            if extra or "item" not in value:
                raise TemplateError("$repeat objects must have exactly the keys '$repeat' and 'item'")
            if not isinstance(value["$repeat"], (int, str)) or isinstance(value["$repeat"], bool):
                raise TemplateError("$repeat must be an integer or a placeholder string")
        for item in value.values():
            validate(item)


def _lookup_path(data: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        elif isinstance(data, list) and part.isdigit() and int(part) < len(data):
            data = data[int(part)]
        else:
            return MISSING
    return data


def _parse_default(default: str) -> Any:
    try:
        return json.loads(default)
    except ValueError:
        return default


def evaluate(expr: str, ctx: RenderContext) -> Any:
    name, default = _split_default(expr)
    value = _evaluate(name, ctx)
    if value is MISSING or value is None:
        return _parse_default(default) if default is not None else None
    return value


def _evaluate(name: str, ctx: RenderContext) -> Any:
    rng = ctx.rng
    match = _REQUEST_RE.match(name)
    if match:
        source, key = match.groups()
        if source == "params":
            return ctx.params.get(key, MISSING)
        if source == "query":
            return ctx.query.get(key, MISSING)
        if source == "headers":
            lowered = {k.lower(): v for k, v in ctx.headers.items()}
            return lowered.get(key.lower(), MISSING)
        return _lookup_path(ctx.body, key)
    match = _RANDOM_NUM_RE.match(name)
    if match:
        kind, low, high = match.groups()
        if kind == "int":
            return rng.randint(int(float(low)), int(float(high)))
        return round(rng.uniform(float(low), float(high)), 4)
    match = _RANDOM_CHOICE_RE.match(name)
    if match:
        return _parse_default(rng.choice([c.strip() for c in match.group(1).split(",")]))

    if name in ("name", "first_name", "last_name", "email") and ctx.person is None:
        ctx.person = (rng.choice(generators.FIRST_NAMES), rng.choice(generators.LAST_NAMES), rng.randint(1, 999))
    first, last, number = ctx.person or ("", "", 0)
    simple = {
        "uuid": lambda: str(uuid.UUID(int=rng.getrandbits(128), version=4)),
        "now": lambda: generators.iso(ctx.now),
        "date": lambda: ctx.now.date().isoformat(),
        "timestamp": lambda: int(ctx.now.timestamp()),
        "name": lambda: f"{first} {last}",
        "first_name": lambda: first,
        "last_name": lambda: last,
        "email": lambda: f"{first}.{last}{number}@example.com".lower(),
        "phone": lambda: generators.phone_numbers(rng, 1)[0],
        "word": lambda: rng.choice(generators.WORDS),
        "sentence": lambda: generators._sentence(rng),
        "paragraph": lambda: generators._paragraph(rng),
        "bool": lambda: rng.random() < 0.5,
        "index": lambda: ctx.index if ctx.index is not None else MISSING,
    }
    return simple[name]()


def render(value: Any, ctx: RenderContext) -> Any:
    if isinstance(value, str):
        whole = PLACEHOLDER_RE.fullmatch(value.strip())
        if whole:
            return evaluate(whole.group(1), ctx)

        def substitute(match: re.Match) -> str:
            result = evaluate(match.group(1), ctx)
            if result is None:
                return ""
            return json.dumps(result) if isinstance(result, (dict, list, bool)) else str(result)

        return PLACEHOLDER_RE.sub(substitute, value)
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    if isinstance(value, dict):
        if "$repeat" in value:
            return _render_repeat(value, ctx)
        return {k: render(v, ctx) for k, v in value.items()}
    return value


def _render_repeat(value: Dict[str, Any], ctx: RenderContext) -> List[Any]:
    count = render(value["$repeat"], ctx)
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise TemplateError(f"$repeat must resolve to an integer, got {count!r}") from None
    count = max(0, min(count, MAX_REPEAT))
    outer = ctx.index
    items = []
    outer_person = ctx.person
    for i in range(count):
        ctx.index = i + 1
        ctx.person = None  # a new person per generated item
        items.append(render(value["item"], ctx))
    ctx.index, ctx.person = outer, outer_person
    return items
