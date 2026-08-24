"""Pytest configuration."""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TENSHIN_DEV", "1")


@pytest.fixture
def client():
    from app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_db():
    """Start each test with an empty test ground."""
    import db as db_module
    from engine.test_ground import shutdown_test_ground

    db_module.init_sanctuary_schema()
    c = db_module.db()
    c.execute("TRUNCATE test_ground_tokens, characters RESTART IDENTITY;")
    c.commit()
    yield
    shutdown_test_ground()
