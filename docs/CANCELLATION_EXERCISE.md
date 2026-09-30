# Implement cancellation without reading the answer

Don't open the completed `cancel` function in `app/service.py` yet. Work only in `backend/exercises/cancellation.py`. The normal app stays functional; the exercise checker imports your function directly. It intentionally starts with `NotImplementedError`.

Signature: `cancel(db, reservation_id) → Reservation`. You receive a fresh SQLAlchemy session with no active transaction. The function owns the transaction. Return a usable reservation after commit or raise FastAPI `HTTPException`.

## Acceptance criteria

- Missing reservation: 404, no writes.
- Active reservation: subtract exactly its quantity from the item's reserved count; don't change on_hand; persist status `cancelled` and update `updated_at`.
- Already cancelled: return the existing row; don't change counts or timestamp again.
- Collected: 409, no writes.
- Lock the pickup before touching mutable reservation state, then lock the item. Follow the same protocol as other pickup operations.
- Commit state and counters together; a failure rolls back both.
- Never delete the reservation history.

Run the starter checks (they are expected to fail before you implement the function):

```sh
docker compose --profile test run --rm --build tests sh -c "alembic upgrade head && pytest exercises/check_cancellation.py -v"
```

Rebuild after edits, because the test container copies the source during image build. The checker uses only fictional data and refuses a non-test database. It checks core behavior; add a rollback test and a concurrent cancel-versus-fulfill test for fuller coverage.

## Hints, from smallest to largest

1. Available is derived, so there is no available column to increment.
2. A status check and stock change in separate transactions can both run twice under concurrency.
3. Use `with db.begin()` to group reads/locks/writes and rollback on exceptions.
4. Read only the immutable pickup ID first. Lock that pickup. Then read the reservation's current state. Avoid caching the mutable reservation before the lock.
5. SQLAlchemy builds a locked query using `select(Model).where(...).with_for_update()`.
6. Decide the terminal-state behavior before adjusting counters. Only an active reservation changes inventory.

After passing, compare your code with the completed function and write down one design choice you initially missed. Passing three starter checks alone doesn't prove concurrent correctness; use the application's locking protocol and explain the interleavings.
