"""Settings loading.

Precedence (lowest to highest): built-in defaults < ``config.ini`` < ``MOCKBOX_*``
environment variables < explicit overrides (e.g. CLI flags).
"""

from __future__ import annotations

import logging
import os
import secrets
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Optional, Tuple

from .features import ALL as ALL_FEATURES, FeatureError, parse_features

log = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE = "config.ini"
CONFIG_PATH_ENV = "MOCKBOX_CONFIG"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 5000
    debug: bool = False
    secret_key: str = ""
    admin_api_keys: Tuple[str, ...] = ()
    cors_origins: Tuple[str, ...] = ("*",)
    mocks_files: Tuple[str, ...] = ()
    features: Tuple[str, ...] = ALL_FEATURES
    # True when no secret was configured and a random one was generated.
    secret_key_generated: bool = False

    def with_overrides(self, **overrides) -> "Settings":
        clean = {k: v for k, v in overrides.items() if v is not None}
        if not clean:
            return self
        if clean.get("secret_key"):
            clean["secret_key_generated"] = False
        return finalize(replace(self, **clean))


def _parse_bool(value: str, name: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(f"{name}: expected a boolean (true/false), got {value!r}")


def _parse_port(value: str, name: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise ConfigError(f"{name}: expected an integer port, got {value!r}") from None
    if not 1 <= port <= 65535:
        raise ConfigError(f"{name}: port must be between 1 and 65535, got {port}")
    return port


def _parse_list(value: str, name: str) -> Tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_str(value: str, name: str) -> str:
    return value.strip()


def _parse_features(value: str, name: str) -> Tuple[str, ...]:
    try:
        return parse_features(value)
    except FeatureError as exc:
        raise ConfigError(f"{name}: {exc}") from None


_FIELDS = (
    ("server", "host", "MOCKBOX_HOST", "host", _parse_str),
    ("server", "port", "MOCKBOX_PORT", "port", _parse_port),
    ("server", "debug", "MOCKBOX_DEBUG", "debug", _parse_bool),
    ("server", "secret_key", "MOCKBOX_SECRET_KEY", "secret_key", _parse_str),
    ("server", "cors_origins", "MOCKBOX_CORS_ORIGINS", "cors_origins", _parse_list),
    ("server", "features", "MOCKBOX_FEATURES", "features", _parse_features),
    ("auth", "admin_api_keys", "MOCKBOX_ADMIN_API_KEYS", "admin_api_keys", _parse_list),
    ("mocks", "files", "MOCKBOX_MOCKS", "mocks_files", _parse_list),
)


def resolve_config_path(path: Optional[str], env: Mapping[str, str]) -> Tuple[Path, bool]:
    """Return (path, explicit). A missing explicit path is an error; a missing default is not."""
    if path:
        return Path(path), True
    if env.get(CONFIG_PATH_ENV):
        return Path(env[CONFIG_PATH_ENV]), True
    return Path(DEFAULT_CONFIG_FILE), False


def load_settings(path: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> Settings:
    env = os.environ if env is None else env
    config_path, explicit = resolve_config_path(path, env)

    parser = ConfigParser(interpolation=None)
    if config_path.is_file():
        try:
            parser.read(config_path, encoding="utf-8")
        except ConfigParserError as exc:
            raise ConfigError(f"Could not parse {config_path}: {exc}") from exc
    elif explicit:
        raise ConfigError(f"Config file not found: {config_path}")

    values = {}
    for section, option, env_var, field, parse in _FIELDS:
        if parser.has_option(section, option):
            values[field] = parse(parser.get(section, option), f"[{section}] {option}")
        if env_var in env:
            values[field] = parse(env[env_var], env_var)

    return finalize(Settings(**values))


def finalize(settings: Settings) -> Settings:
    """Fill in derived values (currently: a random secret key when none is configured)."""
    if settings.secret_key:
        return settings
    log.warning(
        "No secret_key configured; using a random one. JWTs will stop validating when the "
        "server restarts. Set [server] secret_key or MOCKBOX_SECRET_KEY to keep them stable."
    )
    return replace(settings, secret_key=secrets.token_hex(32), secret_key_generated=True)
