"""Mock authentication: token issuing, credential parsing and route decorators.

Supported credentials:

* ``Authorization: Bearer <jwt>``            -- a JWT issued by ``POST /api/auth/jwt-token``
* ``Authorization: Bearer <token>``          -- an issued API key or OAuth access token
* ``Authorization: ApiKey <key>``            -- an issued API key (or an admin key)
* ``X-API-Key: <key>``                       -- same as ``ApiKey``
* ``Authorization: Basic <base64(user:pw)>`` -- any username/password is accepted (it's a mock)

State (issued tokens, runtime admin keys) is held in memory per app instance, so it is lost on
restart and is not shared between worker processes.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import jwt
from flask import current_app, g, request

from .errors import ApiError

EXTENSION_KEY = "mockbox.auth"

JWT_ALGORITHM = "HS256"
JWT_DEFAULT_TTL = 24 * 3600
JWT_MAX_TTL = 30 * 24 * 3600
RESERVED_JWT_CLAIMS = frozenset({"exp", "iat", "nbf"})
OAUTH_ACCESS_TTL = 3600
OAUTH_REFRESH_TTL = 30 * 24 * 3600

SCHEMES = ("jwt", "bearer", "api_key", "basic")
_WWW_AUTHENTICATE = {
    "jwt": 'Bearer realm="mock-box"',
    "bearer": 'Bearer realm="mock-box"',
    "api_key": 'ApiKey realm="mock-box"',
    "basic": 'Basic realm="mock-box"',
}


@dataclass(frozen=True)
class AuthContext:
    type: str
    user: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"type": self.type}
        if self.user is not None:
            data["user"] = self.user
        return data


@dataclass
class IssuedToken:
    kind: str  # "api_key" | "oauth_access" | "oauth_refresh"
    created_at: float
    expires_at: Optional[float] = None
    linked: Optional[str] = None  # access <-> refresh token pairing
    scope: Optional[str] = None

    def expired(self, now: float) -> bool:
        return self.expires_at is not None and now >= self.expires_at


def mask(secret: str) -> str:
    return secret if len(secret) <= 10 else f"{secret[:6]}...{secret[-4:]}"


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class AuthManager:
    def __init__(self, secret_key: str, admin_keys: Iterable[str] = (), clock: Callable[[], float] = time.time):
        if not secret_key:
            raise ValueError("secret_key must not be empty")
        self._secret_key = secret_key
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens: Dict[str, IssuedToken] = {}
        self._config_admin_keys = frozenset(admin_keys)
        self._runtime_admin_keys: set = set()

    # ------------------------------------------------------------------ issued tokens
    def _purge_expired(self, now: float) -> None:
        for token in [t for t, info in self._tokens.items() if info.expired(now)]:
            del self._tokens[token]

    def issue_api_key(self) -> str:
        key = f"mock_{secrets.token_hex(16)}"
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            self._tokens[key] = IssuedToken("api_key", created_at=now)
        return key

    def issue_oauth_token(self, scope: str = "read write") -> Dict[str, Any]:
        access = f"oauth_{secrets.token_hex(20)}"
        refresh = f"refresh_{secrets.token_hex(20)}"
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            self._tokens[access] = IssuedToken("oauth_access", now, now + OAUTH_ACCESS_TTL, refresh, scope)
            self._tokens[refresh] = IssuedToken("oauth_refresh", now, now + OAUTH_REFRESH_TTL, access, scope)
        return {
            "access_token": access,
            "token_type": "bearer",
            "expires_in": OAUTH_ACCESS_TTL,
            "refresh_token": refresh,
            "scope": scope,
        }

    def refresh_oauth_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Rotate a refresh token: revoke the old pair and issue a new one."""
        with self._lock:
            info = self._tokens.get(refresh_token)
            if info is None or info.kind != "oauth_refresh" or info.expired(self._clock()):
                return None
            self._tokens.pop(refresh_token, None)
            if info.linked:
                self._tokens.pop(info.linked, None)
            scope = info.scope or "read write"
        return self.issue_oauth_token(scope)

    def is_valid_token(self, token: str, kinds: Tuple[str, ...] = ("api_key", "oauth_access")) -> bool:
        with self._lock:
            info = self._tokens.get(token)
            return info is not None and info.kind in kinds and not info.expired(self._clock())

    def list_tokens(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._purge_expired(self._clock())
            return [
                {
                    "token": token,
                    "kind": info.kind,
                    "created_at": _iso(info.created_at),
                    "expires_at": _iso(info.expires_at),
                }
                for token, info in self._tokens.items()
            ]

    def clear_tokens(self) -> int:
        with self._lock:
            count = len(self._tokens)
            self._tokens.clear()
            return count

    # ------------------------------------------------------------------ admin keys
    @property
    def admin_enabled(self) -> bool:
        return bool(self._config_admin_keys or self._runtime_admin_keys)

    def is_admin_key(self, key: str) -> bool:
        with self._lock:
            candidates = list(self._config_admin_keys | self._runtime_admin_keys)
        # Compare against every key so timing doesn't reveal which prefix matched.
        matched = False
        for candidate in candidates:
            matched |= hmac.compare_digest(candidate.encode(), key.encode())
        return matched

    def add_admin_key(self, key: Optional[str] = None) -> str:
        key = key or f"admin_{secrets.token_hex(16)}"
        with self._lock:
            self._runtime_admin_keys.add(key)
        return key

    def remove_admin_key(self, key: str) -> str:
        """Return "removed", "protected" (defined in config) or "missing"."""
        with self._lock:
            if key in self._config_admin_keys:
                return "protected"
            if key in self._runtime_admin_keys:
                self._runtime_admin_keys.discard(key)
                return "removed"
            return "missing"

    def list_admin_keys(self) -> List[Dict[str, str]]:
        with self._lock:
            config_keys = sorted(self._config_admin_keys)
            runtime_keys = sorted(self._runtime_admin_keys)
        return [{"key": mask(k), "source": "config"} for k in config_keys] + [
            {"key": mask(k), "source": "runtime"} for k in runtime_keys
        ]

    # ------------------------------------------------------------------ JWT
    def issue_jwt(self, claims: Dict[str, Any], ttl: int = JWT_DEFAULT_TTL) -> str:
        now = datetime.fromtimestamp(self._clock(), tz=timezone.utc)
        payload = {k: v for k, v in claims.items() if k not in RESERVED_JWT_CLAIMS}
        payload.update(iat=now, exp=now + timedelta(seconds=ttl))
        return jwt.encode(payload, self._secret_key, algorithm=JWT_ALGORITHM)

    def decode_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(
                token,
                self._secret_key,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp", "iat"]},
            )
        except jwt.InvalidTokenError:
            return None


def get_auth_manager() -> AuthManager:
    return current_app.extensions[EXTENSION_KEY]


# ---------------------------------------------------------------------- credential parsing
def _presented_credentials() -> Tuple[str, str]:
    """Return (scheme, value) with scheme lower-cased; ("", "") when nothing was sent."""
    header = request.headers.get("Authorization", "").strip()
    if header:
        scheme, _, value = header.partition(" ")
        return scheme.lower(), value.strip()
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return "apikey", api_key
    return "", ""


def _decode_basic(value: str) -> Optional[str]:
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    username, sep, _password = decoded.partition(":")
    return username if sep and username else None


def resolve_auth(allowed: Iterable[str]) -> Optional[AuthContext]:
    """Authenticate the current request against the allowed schemes."""
    allowed = set(allowed)
    scheme, value = _presented_credentials()
    if not value:
        return None
    manager = get_auth_manager()

    if scheme == "bearer":
        if allowed & {"jwt", "bearer"}:
            claims = manager.decode_jwt(value)
            if claims is not None:
                return AuthContext("jwt", claims)
        if "bearer" in allowed and (manager.is_valid_token(value) or manager.is_admin_key(value)):
            return AuthContext("bearer")
    elif scheme == "apikey":
        if "api_key" in allowed and (manager.is_valid_token(value, ("api_key",)) or manager.is_admin_key(value)):
            return AuthContext("api_key")
    elif scheme == "basic":
        if "basic" in allowed:
            username = _decode_basic(value)
            if username is not None:
                return AuthContext("basic", {"username": username})
    return None


def require_auth(*schemes: str):
    """Protect a view. ``require_auth()`` accepts every scheme; pass names to restrict.

    The resulting :class:`AuthContext` is stored on ``flask.g.auth``.
    """
    allowed = tuple(schemes) or SCHEMES
    unknown = set(allowed) - set(SCHEMES)
    if unknown:
        raise ValueError(f"Unknown auth scheme(s): {sorted(unknown)}; expected {SCHEMES}")
    challenge = ", ".join(dict.fromkeys(_WWW_AUTHENTICATE[s] for s in allowed))

    def decorator(view):
        view.auth_schemes = allowed  # used by docs/tests

        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return view(*args, **kwargs)
            if not _presented_credentials()[1]:
                raise ApiError(401, "Authentication required", {"WWW-Authenticate": challenge})
            context = resolve_auth(allowed)
            if context is None:
                raise ApiError(
                    401,
                    f"Invalid or expired credentials (accepted: {', '.join(allowed)})",
                    {"WWW-Authenticate": challenge},
                )
            g.auth = context
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_admin(view):
    """Protect a view with a configured admin API key (ApiKey, Bearer or X-API-Key)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == "OPTIONS":
            return view(*args, **kwargs)
        manager = get_auth_manager()
        if not manager.admin_enabled:
            raise ApiError(
                403,
                "Admin API is disabled. Configure [auth] admin_api_keys in config.ini "
                "or the MOCKBOX_ADMIN_API_KEYS environment variable.",
            )
        scheme, value = _presented_credentials()
        if not value:
            raise ApiError(401, "Admin API key required", {"WWW-Authenticate": 'ApiKey realm="mock-box admin"'})
        if scheme not in ("apikey", "bearer") or not manager.is_admin_key(value):
            raise ApiError(403, "Credentials are not a valid admin API key")
        g.auth = AuthContext("admin")
        return view(*args, **kwargs)

    return wrapped
