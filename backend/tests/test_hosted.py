import pytest
from fastapi.testclient import TestClient
from app.hosted import create_app


@pytest.fixture
def hosted(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<h1>GiveHold</h1>")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    return TestClient(create_app())


def test_demo_is_public(hosted):
    for path in ["/", "/api/items", "/api/docs"]:
        response = hosted.get(path)
        assert response.status_code == 200
        assert "www-authenticate" not in response.headers


def test_demo_serves_real_api_and_frontend(hosted):
    assert "GiveHold" in hosted.get("/").text
    response = hosted.get("/api/items")
    assert response.status_code == 200 and len(response.json()) == 3
    assert response.headers["cache-control"] == "no-store"
    assert hosted.get("/health").status_code == 200


def test_demo_rejects_cross_origin_mutation(hosted):
    response = hosted.post("/api/pickups/00000000-0000-0000-0000-000000000001/fulfill",
                           headers={"Origin": "https://unrelated.example"})
    assert response.status_code == 403


def test_public_demo_can_reserve_and_cancel(hosted):
    from uuid import uuid4
    response = hosted.post("/api/reservations", json={
        "request_key": str(uuid4()),
        "pickup_id": "00000000-0000-0000-0000-000000000001",
        "item_id": 1,
        "quantity": 1,
    })
    assert response.status_code == 200
    reservation = response.json()
    assert reservation["status"] == "active"
    assert hosted.post(f"/api/reservations/{reservation['id']}/cancel").json()["status"] == "cancelled"
