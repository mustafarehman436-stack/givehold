"""Creates isolated fictional demo records; does not reset existing inventory."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    with httpx.Client(base_url=base, timeout=15) as client:
        volunteers = client.get("/volunteers").raise_for_status().json()
        assert len(volunteers) >= 2, "Run the fictional seed first"
        item = (
            client.post(
                "/items",
                json={
                    "name": "Demo last blanket " + str(uuid4())[:8],
                    "category": "Demo",
                    "condition": "new",
                    "on_hand": 1,
                },
            )
            .raise_for_status()
            .json()
        )
        pickups = []
        for volunteer in volunteers[:2]:
            pickups.append(
                client.post(
                    "/pickups",
                    json={"id": str(uuid4()), "volunteer_id": volunteer["id"]},
                )
                .raise_for_status()
                .json()
            )
    barrier = Barrier(2)

    def reserve(index):
        # Independent HTTP sessions; the integration test proves lock overlap.
        with httpx.Client(base_url=base, timeout=15) as session:
            barrier.wait(timeout=5)
            response = session.post(
                "/reservations",
                json={
                    "request_key": str(uuid4()),
                    "pickup_id": pickups[index]["id"],
                    "item_id": item["id"],
                    "quantity": 1,
                },
            )
            return volunteers[index]["name"], response

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [0, 1]))
    for name, response in results:
        print(name, response.status_code, response.json())
    assert sorted(r.status_code for _, r in results) == [200, 409]
    with httpx.Client(base_url=base, timeout=15) as client:
        current = next(
            i
            for i in client.get("/items").raise_for_status().json()
            if i["id"] == item["id"]
        )
        reservations = [
            r
            for r in client.get("/reservations").raise_for_status().json()
            if r["item_id"] == item["id"]
        ]
        assert (current["on_hand"], current["reserved"], current["available"]) == (
            1,
            1,
            0,
        )
        assert len(reservations) == 1
    print(
        "PASS: one winner, one out-of-stock response, one reservation; on_hand=1 reserved=1 available=0"
    )


if __name__ == "__main__":
    main()
