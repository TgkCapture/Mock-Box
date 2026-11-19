"""JSON error responses used across the whole server."""

from __future__ import annotations

from http import HTTPStatus
from typing import Mapping, Optional

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Raise from any view to return a JSON error response."""

    def __init__(self, status: int, message: str, headers: Optional[Mapping[str, str]] = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.headers = dict(headers or {})


def status_phrase(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def error_response(status: int, message: str, headers: Optional[Mapping[str, str]] = None):
    body = jsonify({"error": {"status": status, "type": status_phrase(status), "message": message}})
    return body, status, dict(headers or {})


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.status, exc.message, exc.headers)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        headers = {}
        if exc.code == 405 and exc.valid_methods:
            headers["Allow"] = ", ".join(exc.valid_methods)
        return error_response(exc.code or 500, exc.description or status_phrase(exc.code or 500), headers)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.exception("Unhandled error")
        return error_response(500, "Internal server error")
