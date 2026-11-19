"""Command line entry point: ``mockbox`` or ``python -m mockbox``."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from . import __version__
from .app import create_app
from .config import ConfigError, load_settings

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mockbox", description="Run the Mock-Box mock API server.")
    parser.add_argument("-c", "--config", help="Path to a config.ini file (default: ./config.ini if present)")
    parser.add_argument("--host", help="Interface to bind (default: 127.0.0.1)")
    parser.add_argument("-p", "--port", type=int, help="Port to listen on (default: 5000)")
    parser.add_argument("--debug", action=argparse.BooleanOptionalAction, default=None, help="Enable Flask debug mode")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        settings = load_settings(args.config).with_overrides(host=args.host, port=args.port, debug=args.debug)
        if not 1 <= settings.port <= 65535:
            raise ConfigError(f"--port must be between 1 and 65535, got {settings.port}")
    except ConfigError as exc:
        print(f"mockbox: configuration error: {exc}", file=sys.stderr)
        return 2

    if settings.host not in LOOPBACK_HOSTS:
        logging.getLogger("mockbox").warning(
            "Binding to %s exposes the mock server beyond this machine. Mock-Box accepts any Basic "
            "credentials and issues tokens to anyone; only do this on a trusted network.",
            settings.host,
        )
    if settings.debug and settings.host not in LOOPBACK_HOSTS:
        logging.getLogger("mockbox").warning("Debug mode on a non-loopback host allows remote code execution.")

    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
