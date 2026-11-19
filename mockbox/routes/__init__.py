"""Blueprint wiring.

Layout::

    /                 pages      (home, health, docs, openapi.json)
    /api/auth/...     auth       (token issuing and verification)
    /api/admin/...    admin      (admin-key protected management)
    /api/inspector/.. inspector  (recorded request history; page at /inspect)
    /api/...          mock data  (all share the ?count/?seed/?delay/?status controls)

To add a mock endpoint: create a module with a Blueprint, add it to ``MOCK_BLUEPRINTS``
and document it in ``mockbox/openapi.py`` (the test suite checks the two stay in sync).
"""

from __future__ import annotations

from flask import Blueprint, Flask

from ..controls import apply_controls
from . import (
    activities,
    admin,
    auth,
    content,
    credit_lines,
    data,
    echo,
    inspector,
    mocks,
    orders,
    pages,
    phone_numbers,
    products,
    rss_feed,
    simulate,
    store,
    users,
)

MOCK_BLUEPRINTS = (
    phone_numbers.bp,
    data.bp,
    products.bp,
    users.bp,
    orders.bp,
    rss_feed.bp,
    credit_lines.bp,
    activities.bp,
    simulate.bp,
    echo.bp,
    content.bp,
    store.bp,
)


def register_routes(app: Flask) -> None:
    mock = Blueprint("mock", __name__)
    mock.before_request(apply_controls)
    for bp in MOCK_BLUEPRINTS:
        mock.register_blueprint(bp)

    api = Blueprint("api", __name__, url_prefix="/api")
    api.register_blueprint(auth.bp)
    api.register_blueprint(admin.bp)
    api.register_blueprint(inspector.bp)
    api.register_blueprint(mocks.bp)
    api.register_blueprint(mock)

    app.register_blueprint(pages.bp)
    app.register_blueprint(inspector.page_bp)
    app.register_blueprint(api)
