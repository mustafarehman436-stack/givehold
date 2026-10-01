from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from app.db import engine


def test_pages_search_and_global_totals(client):
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO items(name,category,condition,on_hand,reserved) SELECT 'Extra ' || n, 'Bedding', 'good', 2, 0 FROM generate_series(1,110) AS n"
            )
        )
    first = client.get("/inventory").json()
    second = client.get("/inventory?offset=50").json()
    last = client.get("/inventory?offset=100").json()
    ids = [x["id"] for page in (first, second, last) for x in page["items"]]
    assert len(ids) == len(set(ids)) == first["total"] == 113
    assert ids == sorted(ids)
    assert len(first["items"]) == len(second["items"]) == 50
    assert len(last["items"]) == 13
    assert first["on_hand"] == second["on_hand"] == 241
    found = client.get("/inventory?q=Extra%20110").json()
    assert len(found["items"]) == found["total"] == 1
    assert found["items"][0]["name"] == "Extra 110"
    assert found["on_hand"] == first["on_hand"]
    assert client.get("/inventory?q=%25").json()["total"] == 0
    assert client.get("/inventory?q=missing").json()["items"] == []
    assert client.get("/inventory?offset=1000").json()["items"] == []
    assert len(client.get("/items").json()) == 50


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "q=" + "x" * 101]
)
def test_invalid_pagination(client, query):
    assert client.get("/inventory?" + query).status_code == 422


def test_reservation_name_does_not_depend_on_inventory_page(client):
    item = client.post(
        "/items",
        json={
            "name": "Last-page item",
            "category": "Other",
            "condition": "good",
            "on_hand": 1,
        },
    ).json()
    result = client.post(
        "/reservations",
        json={
            "request_key": str(uuid4()),
            "pickup_id": str(UUID(int=1)),
            "item_id": item["id"],
            "quantity": 1,
        },
    )
    assert result.status_code == 200
    assert client.get("/reservations").json()[0]["item_name"] == "Last-page item"
    summary = client.get("/inventory?limit=1").json()
    assert summary["reserved"] == 1
    assert summary["available"] == summary["on_hand"] - 1
