"""Two real HTTP handlers, two real connections, a verified PostgreSQL lock wait."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic, sleep
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from app.db import engine
from app.main import app
from test_workflow import state


def test_two_volunteers_compete_for_last_unit():
    first_has_lock = Event()
    release_first = Event()
    second_started = Event()
    mutex = Lock()
    pids = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if "FROM items" in statement and "FOR UPDATE" in statement:
            with mutex:
                pids.append(conn.connection.driver_connection.info.backend_pid)
                if len(pids) == 2:
                    second_started.set()

    def after(conn, cursor, statement, parameters, context, executemany):
        if "FROM items" in statement and "FOR UPDATE" in statement:
            if conn.connection.driver_connection.info.backend_pid == pids[0]:
                first_has_lock.set()
                assert release_first.wait(
                    10
                ), "Test timed out waiting to release first transaction"

    def request(volunteer):
        with TestClient(app) as client:
            return client.post(
                "/reservations",
                json={
                    "request_key": str(uuid4()),
                    "pickup_id": str(UUID(int=volunteer)),
                    "item_id": 1,
                    "quantity": 1,
                },
            )

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(request, 1)
            try:
                assert first_has_lock.wait(5)
                second = pool.submit(request, 2)
                assert second_started.wait(5)
                assert (
                    pids[0] != pids[1]
                ), "Requests must use different database connections"
                # Poll database state, not elapsed time, to prove actual overlap.
                deadline = monotonic() + 5
                blocked = False
                with engine.connect() as observer:
                    while monotonic() < deadline:
                        blockers = observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": pids[1]}
                        )
                        if pids[0] in blockers:
                            blocked = True
                            break
                        sleep(0.01)
                assert blocked, "Second transaction never waited for first item lock"
            finally:
                release_first.set()
            responses = [first.result(timeout=5), second.result(timeout=5)]
    finally:
        release_first.set()
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["detail"]
        == "Not enough available stock"
    )
    assert state() == (1, 1, 1)
