"""Command line entry point: ``mockbox`` or ``python -m mockbox``."""

from __future__ import annotations

import argparse
import logging
import os
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
    parser.add_argument(
        "-m", "--mocks", action="append", metavar="FILE",
        help="Custom routes file (JSON or YAML); repeat for several files",
    )
    parser.add_argument("--debug", action=argparse.BooleanOptionalAction, default=None, help="Enable Flask debug mode")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        settings = load_settings(args.config).with_overrides(
            host=args.host, port=args.port, debug=args.debug, mocks_files=tuple(args.mocks) if args.mocks else None
        )
        if not 1 <= settings.port <= 65535:
            raise ConfigError(f"--port must be between 1 and 65535, got {settings.port}")
    except ConfigError as exc:
        print(f"mockbox: configuration error: {exc}", file=sys.stderr)
        return 2

    log = logging.getLogger("mockbox")
    exposed = settings.host not in LOOPBACK_HOSTS
    if exposed and not os.environ.get("MOCKBOX_IN_CONTAINER"):
        log.warning(
            "Binding to %s exposes the mock server beyond this machine. Mock-Box accepts any Basic "
            "credentials and issues tokens to anyone; only do this on a trusted network.",
            settings.host,
        )
    if settings.debug and exposed:
        log.warning("Debug mode on a non-loopback host allows remote code execution.")

    try:
        app = create_app(settings)
    except ConfigError as exc:
        print(f"mockbox: configuration error: {exc}", file=sys.stderr)
        return 2
    serve(app, settings.host, settings.port, settings.debug)
    return 0


def serve(app, host: str, port: int, debug: bool) -> None:
    """Use waitress (``pip install mock-box[server]``) when available, else Flask's dev server.

    Both run a single process, which Mock-Box needs because its state lives in memory.
    """
    if not debug:
        try:
            from waitress import serve as waitress_serve
        except ImportError:
            pass
        else:
            logging.getLogger("mockbox").info("Mock-Box %s listening on http://%s:%s", __version__, host, port)
            waitress_serve(app, host=host, port=port, threads=8, ident="mock-box")
            return
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    sys.exit(main())
