"""Blueprint wiring.

Layout::

    /                 pages      (home, health, docs, openapi.json)
    /api/auth/...     auth       (token issuing and verification)
    /api/admin/...    admin      (admin-key protected management)
    /api/inspector/.. inspector  (recorded request history; page at /inspect)
    /api/...          mock data  (all share the ?count/?seed/?delay/?status controls)

Each mock blueprint belongs to a feature (see ``mockbox/features.py``) and is only registered
when that feature is enabled. To add a mock endpoint: create a module with a Blueprint, add it
to ``FEATURE_BLUEPRINTS`` and document it in ``mockbox/openapi.py`` (the test suite checks the
two stay in sync for every feature combination).
"""

from __future__ import annotations

from typing import Iterable

from flask import Blueprint, Flask

from ..features import ALL as ALL_FEATURES

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
    payments,
    phone_numbers,
    products,
    rss_feed,
    simulate,
    store,
    users,
)

# Blueprints under /api that share the ?count/?seed/?delay/?status controls, by feature.
FEATURE_BLUEPRINTS = {
    "data": (
        phone_numbers.bp,
        data.bp,
        products.bp,
        users.bp,
        orders.bp,
        rss_feed.bp,
        credit_lines.bp,
        activities.bp,
        simulate.bp,
        content.bp,
    ),
    "echo": (echo.bp,),
    "store": (store.bp,),
    "payments": (payments.bp,),
}


def register_routes(app: Flask, features: Iterable[str] = ALL_FEATURES) -> None:
    features = set(features)
    mock = Blueprint("mock", __name__)
    mock.before_request(apply_controls)
    for feature, blueprints in FEATURE_BLUEPRINTS.items():
        if feature in features:
            for bp in blueprints:
                mock.register_blueprint(bp)

    api = Blueprint("api", __name__, url_prefix="/api")
    if "auth" in features:
        api.register_blueprint(auth.bp)
    if "admin" in features:
        api.register_blueprint(admin.bp)
    if "inspector" in features:
        api.register_blueprint(inspector.bp)
        app.register_blueprint(inspector.page_bp)
    api.register_blueprint(mocks.bp)
    api.register_blueprint(mock)

    app.register_blueprint(pages.bp)
    if "docs" in features:
        app.register_blueprint(pages.docs_bp)
    app.register_blueprint(api)
