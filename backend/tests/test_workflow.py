from uuid import UUID, uuid4
import pytest
from sqlalchemy import event, select, text
from app.db import Session, engine
from app.models import Item, Reservation

PICKUP = str(UUID(int=1))


def payload(**changes):
    return dict(
        request_key=str(uuid4()), pickup_id=PICKUP, item_id=1, quantity=1, **changes
    )


def state():
    with Session() as db:
        item = db.get(Item, 1)
        return item.on_hand, item.reserved, len(list(db.scalars(select(Reservation))))


def test_reservation_replay_and_key_conflict(client):
    data = payload()
    first = client.post("/reservations", json=data)
    assert first.status_code == 200
    assert client.post("/reservations", json=data).json()["id"] == first.json()["id"]
    assert client.post("/reservations", json={**data, "quantity": 2}).status_code == 409
    assert state() == (1, 1, 1)


def test_cancel_twice_and_replay_cancelled_request(client):
    data = payload()
    reservation = client.post("/reservations", json=data).json()
    for _ in range(2):
        response = client.post(f"/reservations/{reservation['id']}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    assert client.post("/reservations", json=data).json()["status"] == "cancelled"
    assert state() == (1, 0, 1)
    assert client.post("/reservations", json=payload()).status_code == 200
    assert state() == (1, 1, 2)


def test_fulfill_twice_then_reject_cancel_and_new_reservation(client):
    reservation = client.post("/reservations", json=payload()).json()
    for _ in range(2):
        assert client.post(f"/pickups/{PICKUP}/fulfill").status_code == 200
    assert client.post(f"/reservations/{reservation['id']}/cancel").status_code == 409
    assert client.post("/reservations", json=payload()).status_code == 409
    assert state() == (0, 0, 1)
    assert (
        next(p for p in client.get("/pickups").json() if p["id"] == PICKUP)[
            "fulfilled_at"
        ]
        is not None
    )


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "1", 1000001])
def test_invalid_quantity(client, quantity):
    assert (
        client.post(
            "/reservations", json={**payload(), "quantity": quantity}
        ).status_code
        == 422
    )
    assert state() == (1, 0, 0)


def test_out_of_stock_and_empty_pickup(client):
    assert (
        client.post("/reservations", json={**payload(), "quantity": 2}).status_code
        == 409
    )
    assert client.post(f"/pickups/{PICKUP}/fulfill").status_code == 409
    assert state() == (1, 0, 0)


def test_item_management_and_reserved_floor(client):
    data = {
        "name": "Blanket",
        "category": "Bedding",
        "condition": "good",
        "on_hand": -1,
    }
    assert client.post("/items", json=data).status_code == 422
    assert client.post("/items", json={**data, "on_hand": 5}).status_code == 201
    client.post("/reservations", json=payload())
    assert client.put("/items/1", json={**data, "on_hand": 0}).status_code == 409
    assert client.put("/items/1", json={**data, "on_hand": 3}).status_code == 200
    assert state() == (3, 1, 1)


def test_pickup_replay(client):
    data = {"id": str(uuid4()), "volunteer_id": 1}
    assert client.post("/pickups", json=data).status_code == 200
    assert client.post("/pickups", json=data).status_code == 200
    assert client.post("/pickups", json={**data, "volunteer_id": 2}).status_code == 409
    assert len(client.get("/pickups").json()) == 3


def test_rollback_when_insert_fails_after_counter_update(client):
    saw_update = []

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE items"):
            saw_update.append(True)
        if statement.startswith("INSERT INTO reservations"):
            raise RuntimeError("Injected insert failure")

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="Injected insert failure"):
            client.post("/reservations", json=payload())
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)
    assert saw_update
    assert state() == (1, 0, 0)


def test_database_constraint_rejects_negative_stock():
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE items SET on_hand=-1 WHERE id=1"))
    assert state() == (1, 0, 0)


def test_multi_item_fulfillment_keeps_cancelled_history(client):
    first = client.post("/reservations", json=payload()).json()
    client.post(f"/reservations/{first['id']}/cancel")
    client.post("/reservations", json={**payload(), "item_id": 2, "quantity": 3})
    client.post("/reservations", json={**payload(), "item_id": 3, "quantity": 2})
    assert client.post(f"/pickups/{PICKUP}/fulfill").status_code == 200
    items = {i["id"]: i for i in client.get("/items").json()}
    assert (items[1]["on_hand"], items[2]["on_hand"], items[3]["on_hand"]) == (1, 5, 10)
    assert all(i["reserved"] == 0 for i in items.values())
    assert sorted(r["status"] for r in client.get("/reservations").json()) == [
        "cancelled",
        "collected",
        "collected",
    ]


def test_fulfillment_rolls_back_all_items_on_failure(client):
    client.post("/reservations", json=payload())
    client.post("/reservations", json={**payload(), "item_id": 2, "quantity": 2})

    def fail_history_update(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE reservations"):
            raise RuntimeError("Injected history failure")

    event.listen(engine, "before_cursor_execute", fail_history_update)
    try:
        with pytest.raises(RuntimeError, match="Injected history failure"):
            client.post(f"/pickups/{PICKUP}/fulfill")
    finally:
        event.remove(engine, "before_cursor_execute", fail_history_update)
    items = client.get("/items").json()
    assert (items[0]["on_hand"], items[0]["reserved"]) == (1, 1)
    assert (items[1]["on_hand"], items[1]["reserved"]) == (8, 2)
    assert all(r["status"] == "active" for r in client.get("/reservations").json())
    assert (
        next(p for p in client.get("/pickups").json() if p["id"] == PICKUP)["status"]
        == "open"
    )


@pytest.mark.parametrize(
    "path,payload_data",
    [
        ("/reservations", {"pickup_id": str(UUID(int=999))}),
        ("/reservations", {"item_id": 999}),
    ],
)
def test_missing_resources(client, path, payload_data):
    assert client.post(path, json={**payload(), **payload_data}).status_code == 404
    assert state() == (1, 0, 0)
