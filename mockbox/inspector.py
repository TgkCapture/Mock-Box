"""Records recent /api requests so developers can see exactly what their client sent.

Kept in memory (a ring buffer), so history is lost on restart. Credentials are masked
because anyone who can reach the server can read the history.
"""

from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from flask import Flask, g, request
from werkzeug.exceptions import HTTPException

from .auth import mask

EXTENSION_KEY = "mockbox.inspector"
DEFAULT_HISTORY = 200
MAX_BODY_PREVIEW = 4096
SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie", "proxy-authorization"}
# Requests to these prefixes are not recorded (the inspector would otherwise record itself).
IGNORED_PREFIXES = ("/api/inspector",)


def mask_header(name: str, value: str) -> str:
    if name.lower() not in SENSITIVE_HEADERS:
        return value
    scheme, sep, secret = value.partition(" ")
    if name.lower() in ("authorization", "proxy-authorization") and sep:
        return f"{scheme} {mask(secret) if len(secret) > 10 else '***'}"
    return mask(value) if len(value) > 10 else "***"


def body_preview(data: bytes, limit: int = MAX_BODY_PREVIEW) -> Dict[str, Any]:
    if not data:
        return {"size": 0, "text": None, "truncated": False}
    try:
        text = data[:limit].decode("utf-8")
    except UnicodeDecodeError:
        return {"size": len(data), "text": None, "binary": True, "truncated": False}
    return {"size": len(data), "text": text, "truncated": len(data) > limit}


class Inspector:
    def __init__(self, max_entries: int = DEFAULT_HISTORY):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def record(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            entry["id"] = next(self._ids)
            self._entries.appendleft(entry)

    def list(self, limit: int = 50, method: Optional[str] = None, path: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            entries = list(self._entries)
        if method:
            entries = [e for e in entries if e["method"] == method.upper()]
        if path:
            entries = [e for e in entries if path in e["path"]]
        return entries[:limit]

    def get(self, entry_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return next((e for e in self._entries if e["id"] == entry_id), None)

    def clear(self) -> int:
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def init_app(self, app: Flask) -> None:
        app.extensions[EXTENSION_KEY] = self

        @app.before_request
        def _start_timer():
            g.inspector_start = time.perf_counter()
            if self._should_record():
                request.get_data(cache=True)  # keep a copy; form parsing still works afterwards

        @app.after_request
        def _record(response):
            if self._should_record():
                started = g.get("inspector_start", time.perf_counter())
                self.record({
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "method": request.method,
                    "path": request.path,
                    "query": request.query_string.decode("latin-1"),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "client": request.remote_addr,
                    "request_headers": {k: mask_header(k, v) for k, v in request.headers.items()},
                    "request_body": body_preview(self._captured_body()),
                    "response_headers": dict(response.headers),
                    "response_size": response.calculate_content_length(),
                })
            return response

    @staticmethod
    def _captured_body() -> bytes:
        try:
            return request.get_data(cache=True)
        except HTTPException:  # e.g. body over MAX_CONTENT_LENGTH; the 413 is already being returned
            return b""

    @staticmethod
    def _should_record() -> bool:
        if request.method == "OPTIONS" or request.path.startswith(IGNORED_PREFIXES):
            return False
        return request.path.startswith("/api/") or g.get("custom_route") is not None


def get_inspector() -> Inspector:
    from flask import current_app

    return current_app.extensions[EXTENSION_KEY]
