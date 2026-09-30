import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.db import engine
from app.main import app
from app.seed import seed


@pytest.fixture(autouse=True)
def clean_database():
    # Fail closed: never truncate a normal application database.
    assert engine.dialect.name == "postgresql", "Real PostgreSQL required"
    assert engine.url.database.endswith("_test"), "Use a disposable *_test database"
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE reservations, pickups, items, volunteers RESTART IDENTITY CASCADE"
            )
        )
    seed()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
