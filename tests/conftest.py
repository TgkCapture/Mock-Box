import base64

import pytest

from mockbox import create_app
from mockbox.config import Settings

ADMIN_KEY = "test-admin-key-0123456789"


@pytest.fixture
def make_app():
    def factory(**overrides):
        settings = Settings(secret_key="test-secret-" + "x" * 32, admin_api_keys=(ADMIN_KEY,))
        app = create_app(settings.with_overrides(**overrides) if overrides else settings)
        app.testing = True
        return app

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers():
    return {"X-API-Key": ADMIN_KEY}


def basic(user="jane", password="secret"):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
