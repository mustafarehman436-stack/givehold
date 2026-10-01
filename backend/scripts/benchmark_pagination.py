"""Compare the original full-list handler with the paginated inventory handler.

DESTRUCTIVE: only use an isolated, migrated PostgreSQL *_test database.
The baseline route exists in this script only, never in the deployed app.
"""

import json
import math
import platform
import statistics
from time import perf_counter
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.db import engine
from app.main import app, database, record
from app.models import Item
from app.seed import seed


@app.get("/benchmark-original-items")
def original_items(db=Depends(database)):
    return [record(x) for x in db.scalars(select(Item).order_by(Item.id))]


def reset():
    if engine.dialect.name != "postgresql" or not engine.url.database.endswith("_test"):
        raise RuntimeError("Use a disposable PostgreSQL *_test database")
    with engine.begin() as db:
        db.execute(
            text(
                "TRUNCATE reservations, pickups, items, volunteers RESTART IDENTITY CASCADE"
            )
        )


def run():
    reset()
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO items(name,category,condition,on_hand,reserved) SELECT 'Item ' || n, 'Bedding', 'good', 10, 0 FROM generate_series(1,10000) AS n"
                )
            )
            db.execute(text("ANALYZE items"))
        results = []
        paths = {
            "original": "/benchmark-original-items",
            "paginated": "/inventory?limit=50&offset=0",
        }
        with TestClient(app) as client:
            # Validate the work each endpoint returns, outside measured samples.
            original = client.get(paths["original"]).json()
            page = client.get(paths["paginated"]).json()
            assert len(original) == page["total"] == 10000
            assert page["items"] == original[:50]
            assert page["on_hand"] == sum(x["on_hand"] for x in original) == 100000
            for path in paths.values():
                for _ in range(5):
                    assert client.get(path).status_code == 200
            for repeat in range(5):
                # Alternate endpoint order each repetition to limit order bias.
                order = list(paths) if repeat % 2 == 0 else list(reversed(paths))
                for name in order:
                    samples = []
                    for _ in range(50):
                        start = perf_counter()
                        response = client.get(paths[name])
                        samples.append((perf_counter() - start) * 1000)
                        assert response.status_code == 200
                    samples.sort()
                    results.append(
                        {
                            "name": name,
                            "repeat": repeat + 1,
                            "samples": 50,
                            "median_ms": statistics.median(samples),
                            "p95_ms": samples[math.ceil(len(samples) * 0.95) - 1],
                            "response_bytes": len(response.content),
                        }
                    )
        with engine.connect() as db:
            pg = db.scalar(text("SHOW server_version"))
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "os": platform.platform(),
                    "postgresql": pg,
                    "items": 10000,
                    "page_size": 50,
                    "results": results,
                },
                indent=2,
            )
        )
    finally:
        reset()
        seed()


if __name__ == "__main__":
    run()
