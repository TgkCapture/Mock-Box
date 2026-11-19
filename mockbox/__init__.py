"""Mock-Box: a configurable mock API server for testing HTTP clients."""

__version__ = "0.1.0"

from .app import create_app  # noqa: E402

__all__ = ["create_app", "__version__"]
