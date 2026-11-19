"""User-defined mock routes loaded from JSON or YAML files.

Custom routes are matched before the built-in routes, so they can add new endpoints at any
path *or* override a built-in one. Files are re-read automatically when they change; an
invalid edit keeps the previous routes active and is reported at ``GET /api/mocks``.

See ``examples/mocks.yaml`` for the full format.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from flask import Flask, Response, g, jsonify, request

from . import templating
from .auth import SCHEMES, require_auth
from .controls import apply_controls, now, rng

log = logging.getLogger(__name__)

EXTENSION_KEY = "mockbox.custom_routes"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
ROUTE_KEYS = {"method", "path", "status", "headers", "body", "body_file", "content_type", "delay_ms", "auth", "responses", "mode", "description"}
RESPONSE_KEYS = {"when", "status", "headers", "body", "body_file", "content_type", "delay_ms"}
WHEN_KEYS = {"query", "headers", "body", "params"}
MAX_DELAY_MS = 30_000
MAX_FILE_BYTES = 10 * 1024 * 1024
RELOAD_INTERVAL = 1.0
# Built-in table only: the default guesser also reads the OS registry, which differs per machine.
_MIME_TYPES = mimetypes.MimeTypes()
_PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class MockFileError(ValueError):
    """A mocks file is missing, unparsable or invalid."""


@dataclass
class MockResponse:
    status: int = 200
    headers: Dict[str, Any] = field(default_factory=dict)
    body: Any = None
    raw: Optional[bytes] = None
    content_type: Optional[str] = None
    delay_ms: int = 0
    when: Optional[Dict[str, Dict[str, Any]]] = None


@dataclass
class MockRoute:
    methods: frozenset
    path: str
    regex: re.Pattern
    default: MockResponse
    responses: List[MockResponse]
    mode: str = "match"
    auth: Optional[Tuple[str, ...]] = None
    description: str = ""
    source: str = ""
    _calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def next_sequence_response(self) -> MockResponse:
        with self._lock:
            response = self.responses[self._calls % len(self.responses)]
            self._calls += 1
            return response

    def summary(self) -> Dict[str, Any]:
        return {
            "methods": sorted(self.methods),
            "path": self.path,
            "description": self.description,
            "mode": self.mode,
            "responses": len(self.responses) + 1,
            "auth": list(self.auth) if self.auth else None,
            "source": self.source,
        }


# --------------------------------------------------------------------------- parsing
def _fail(where: str, message: str):
    raise MockFileError(f"{where}: {message}")


def _check_keys(data: Dict[str, Any], allowed: set, where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        _fail(where, f"unknown key(s) {sorted(unknown)}; allowed: {sorted(allowed)}")


def _compile_path(path: Any, where: str) -> re.Pattern:
    if not isinstance(path, str) or not path.startswith("/"):
        _fail(where, "path must be a string starting with '/'")
    normalized = path.rstrip("/") or "/"
    pattern, last = "", 0
    for match in _PARAM_RE.finditer(normalized):
        pattern += re.escape(normalized[last : match.start()]) + f"(?P<{match.group(1)}>[^/]+)"
        last = match.end()
    pattern += re.escape(normalized[last:])
    if "{" in _PARAM_RE.sub("", normalized) or "}" in _PARAM_RE.sub("", normalized):
        _fail(where, "path parameters must look like {name} (letters, digits, underscore)")
    try:
        return re.compile(f"^{pattern}$")
    except re.error as exc:
        _fail(where, f"invalid path ({exc})")


def _parse_response(data: Dict[str, Any], base_dir: Path, where: str, allowed: set) -> MockResponse:
    _check_keys(data, allowed, where)
    status = data.get("status", 200)
    if not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599:
        _fail(where, "status must be an integer between 100 and 599")
    headers = data.get("headers", {})
    if not isinstance(headers, dict):
        _fail(where, "headers must be a mapping")
    delay = data.get("delay_ms", 0)
    if not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= MAX_DELAY_MS:
        _fail(where, f"delay_ms must be an integer between 0 and {MAX_DELAY_MS}")
    if "body" in data and "body_file" in data:
        _fail(where, "use either body or body_file, not both")

    response = MockResponse(status=status, headers=headers, body=data.get("body"), content_type=data.get("content_type"), delay_ms=delay)
    if "body_file" in data:
        file = (base_dir / str(data["body_file"])).resolve()
        if not file.is_file():
            _fail(where, f"body_file not found: {file}")
        if file.stat().st_size > MAX_FILE_BYTES:
            _fail(where, f"body_file is larger than {MAX_FILE_BYTES} bytes")
        if file.suffix.lower() == ".json":
            try:
                response.body = json.loads(file.read_text(encoding="utf-8"))
            except ValueError as exc:
                _fail(where, f"body_file is not valid JSON ({exc})")
        else:
            response.raw = file.read_bytes()
            response.content_type = response.content_type or _MIME_TYPES.guess_type(file.name)[0] or "application/octet-stream"

    try:
        templating.validate(response.body)
        templating.validate(headers)
    except templating.TemplateError as exc:
        _fail(where, str(exc))

    if "when" in data:
        when = data["when"]
        if not isinstance(when, dict) or not when:
            _fail(f"{where}.when", "must be a non-empty mapping")
        _check_keys(when, WHEN_KEYS, f"{where}.when")
        for key, conditions in when.items():
            if not isinstance(conditions, dict):
                _fail(f"{where}.when.{key}", "must be a mapping of name -> expected value")
        response.when = when
    return response


def _parse_route(data: Any, base_dir: Path, where: str, source: str) -> MockRoute:
    if not isinstance(data, dict):
        _fail(where, "each route must be a mapping")
    _check_keys(data, ROUTE_KEYS, where)
    if "path" not in data:
        _fail(where, "path is required")

    methods = data.get("method", "GET")
    methods = [methods] if isinstance(methods, str) else methods
    if not isinstance(methods, list) or not methods:
        _fail(where, "method must be a string or a list of strings")
    methods = {str(m).upper() for m in methods}
    if methods & {"ANY", "*"}:
        methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
    if methods - METHODS:
        _fail(where, f"unsupported method(s) {sorted(methods - METHODS)}")
    if "GET" in methods:
        methods.add("HEAD")

    auth = data.get("auth")
    if auth is not None:
        auth = (auth,) if isinstance(auth, str) else tuple(auth)
        auth = SCHEMES if auth == ("any",) else auth
        if not auth or set(auth) - set(SCHEMES):
            _fail(where, f"auth must be 'any' or one/several of {list(SCHEMES)}")

    mode = data.get("mode", "match")
    if mode not in ("match", "sequence"):
        _fail(where, "mode must be 'match' or 'sequence'")

    responses_data = data.get("responses", [])
    if not isinstance(responses_data, list):
        _fail(where, "responses must be a list")
    responses = [
        _parse_response(r if isinstance(r, dict) else _fail(f"{where}.responses[{i}]", "must be a mapping"),
                        base_dir, f"{where}.responses[{i}]", RESPONSE_KEYS)
        for i, r in enumerate(responses_data)
    ]
    if mode == "sequence":
        if not responses:
            _fail(where, "mode 'sequence' needs a non-empty responses list")
        if any(r.when for r in responses):
            _fail(where, "'when' is not used in mode 'sequence'; remove it or use mode 'match'")

    default_data = {k: v for k, v in data.items() if k in RESPONSE_KEYS - {"when"}}
    return MockRoute(
        methods=frozenset(methods),
        path=data["path"],
        regex=_compile_path(data["path"], where),
        default=_parse_response(default_data, base_dir, where, RESPONSE_KEYS - {"when"}),
        responses=responses,
        mode=mode,
        auth=auth,
        description=str(data.get("description", "")),
        source=source,
    )


def _read_file(path: Path) -> Any:
    if not path.is_file():
        raise MockFileError(f"{path}: file not found")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise MockFileError(f"{path}: YAML support needs PyYAML (pip install 'mock-box[yaml]')") from None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise MockFileError(f"{path}: invalid YAML ({exc})") from None
    try:
        return json.loads(text)
    except ValueError as exc:
        raise MockFileError(f"{path}: invalid JSON ({exc})") from None


def load_routes(files: Iterable[Path]) -> List[MockRoute]:
    routes: List[MockRoute] = []
    for path in files:
        data = _read_file(path)
        if isinstance(data, dict):
            _check_keys(data, {"routes"}, str(path))
            data = data.get("routes", [])
        if not isinstance(data, list):
            raise MockFileError(f"{path}: expected a list of routes or a mapping with a 'routes' list")
        for i, route in enumerate(data):
            routes.append(_parse_route(route, path.parent, f"{path.name}: routes[{i}]", str(path)))
    return routes


# --------------------------------------------------------------------------- runtime
def _matches(expected: Any, actual: Any) -> bool:
    if actual is templating.MISSING or actual is None:
        return False
    if expected == "*":
        return True
    if isinstance(expected, list):
        return any(_matches(e, actual) for e in expected)
    if isinstance(actual, str) and not isinstance(expected, str):
        return actual == (json.dumps(expected) if isinstance(expected, bool) else str(expected))
    return actual == expected


def _when_matches(when: Dict[str, Dict[str, Any]], params: Dict[str, str], body: Any) -> bool:
    headers = {k.lower(): v for k, v in request.headers.items()}
    for source, conditions in when.items():
        for key, expected in conditions.items():
            if source == "query":
                actual = request.args.get(key, templating.MISSING)
            elif source == "headers":
                actual = headers.get(key.lower(), templating.MISSING)
            elif source == "params":
                actual = params.get(key, templating.MISSING)
            else:
                actual = templating._lookup_path(body, key)
            if not _matches(expected, actual):
                return False
    return True


class CustomRoutes:
    def __init__(self, files: Sequence[str] = ()):
        self.files = [Path(f) for f in files]
        self.routes: List[MockRoute] = []
        self.error: Optional[str] = None
        self.loaded_at: Optional[str] = None
        self._mtimes: Dict[Path, float] = {}
        self._last_check = 0.0
        self._lock = threading.Lock()
        if self.files:
            self._load()  # errors at startup are fatal so typos are noticed immediately

    def _stat(self) -> Dict[Path, float]:
        return {f: (f.stat().st_mtime if f.exists() else -1.0) for f in self.files}

    def _load(self) -> None:
        mtimes = self._stat()
        self.routes = load_routes(self.files)
        self._mtimes = mtimes
        self.error = None
        self.loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        log.info("Loaded %d custom route(s) from %s", len(self.routes), ", ".join(map(str, self.files)))

    def maybe_reload(self) -> None:
        if not self.files or time.monotonic() - self._last_check < RELOAD_INTERVAL:
            return
        with self._lock:
            self._last_check = time.monotonic()
            current = self._stat()
            if current == self._mtimes:
                return
            try:
                self._load()
            except MockFileError as exc:
                self._mtimes = current  # don't retry until the file changes again
                self.error = str(exc)
                log.error("Keeping previous custom routes; reload failed: %s", exc)

    def match(self, method: str, path: str) -> Optional[Tuple[MockRoute, Dict[str, str]]]:
        path = path.rstrip("/") or "/"
        for route in self.routes:
            found = route.regex.match(path)
            if found and (method in route.methods or method == "OPTIONS"):
                return route, found.groupdict()
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "files": [str(f) for f in self.files],
            "loaded_at": self.loaded_at,
            "error": self.error,
            "routes": [r.summary() for r in self.routes],
        }

    # ------------------------------------------------------------------ flask
    def init_app(self, app: Flask) -> None:
        app.extensions[EXTENSION_KEY] = self

        @app.before_request
        def serve_custom_route():
            self.maybe_reload()
            found = self.match(request.method, request.path)
            if found is None:
                return None
            route, params = found
            g.custom_route = route
            if request.method == "OPTIONS":
                return Response(status=204)  # CORS preflight; headers added by the CORS hook
            forced = apply_controls()
            if forced is not None:
                return forced
            if route.auth:
                require_auth(*route.auth)(lambda: None)()
            return self._respond(route, params)

    def _respond(self, route: MockRoute, params: Dict[str, str]):
        body = request.get_json(silent=True)
        if route.mode == "sequence":
            chosen = route.next_sequence_response()
        else:
            chosen = next((r for r in route.responses if _when_matches(r.when, params, body)), route.default)

        if chosen.delay_ms:
            time.sleep(chosen.delay_ms / 1000)

        ctx = templating.RenderContext(
            rng=rng(), now=now(), params=params, query=request.args.to_dict(), headers=dict(request.headers), body=body
        )
        headers = {str(k): str(templating.render(v, ctx)) for k, v in chosen.headers.items()}

        if chosen.raw is not None:
            return Response(chosen.raw, status=chosen.status, headers=headers, content_type=chosen.content_type)
        if chosen.body is None:
            return Response(status=chosen.status, headers=headers, content_type=chosen.content_type)
        rendered = templating.render(chosen.body, ctx)
        if isinstance(rendered, str) and not (chosen.content_type or "").endswith("json"):
            return Response(rendered, status=chosen.status, headers=headers, content_type=chosen.content_type or "text/plain; charset=utf-8")
        response = jsonify(rendered)
        response.status_code = chosen.status
        response.headers.update(headers)
        if chosen.content_type:
            response.content_type = chosen.content_type
        return response


def get_custom_routes() -> CustomRoutes:
    from flask import current_app

    return current_app.extensions[EXTENSION_KEY]
