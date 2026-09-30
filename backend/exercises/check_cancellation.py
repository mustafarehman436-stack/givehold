"""Run with: pytest exercises/check_cancellation.py

These checks call only your exercise cancellation implementation.
"""

import pytest
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from app.db import Session, engine
from app.models import Item, Reservation
from app.seed import seed
from app.schemas import ReserveIn
from app.service import reserve, fulfill
from exercises.cancellation import cancel


@pytest.fixture(autouse=True)
def setup():
    assert engine.dialect.name == "postgresql" and engine.url.database.endswith("_test")
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE reservations, pickups, items, volunteers RESTART IDENTITY CASCADE"
            )
        )
    seed()


def make_reservation():
    with Session() as db:
        return reserve(
            db,
            ReserveIn(
                request_key=uuid4(), pickup_id=UUID(int=1), item_id=1, quantity=1
            ),
        ).id


def test_cancel_releases_once():
    reservation_id = make_reservation()
    for _ in range(2):
        with Session() as db:
            assert cancel(db, reservation_id).status == "cancelled"
    with Session() as db:
        item = db.get(Item, 1)
        assert (item.on_hand, item.reserved) == (1, 0)
        assert db.get(Reservation, reservation_id).status == "cancelled"


def test_collected_cannot_be_cancelled():
    reservation_id = make_reservation()
    with Session() as db:
        fulfill(db, str(UUID(int=1)))
    with Session() as db, pytest.raises(HTTPException) as error:
        cancel(db, reservation_id)
    assert error.value.status_code == 409


def test_missing_reservation():
    with Session() as db, pytest.raises(HTTPException) as error:
        cancel(db, 999)
    assert error.value.status_code == 404
