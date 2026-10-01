# Own the project

Use 15–25 focused hours as a planning estimate, not a completion claim. Advance when you can demonstrate the checkpoint without reading a script. Keep a small notebook of predictions, results, and changes you personally make.

## Stage 1 — Run and model the workflow (2–3 hours)

Start Compose, reserve a blanket, cancel, reserve again, and collect. Before every click predict on-hand, reserved, and available counts. Explain why reservation doesn't reduce physical on-hand stock. Draw the four tables from memory and add foreign-key arrows.

Checkpoint: given on_hand=5 and reserved=3, explain why availability is 2; cancellation of 2 changes reserved to 1; collecting the remaining 1 changes on_hand to 4 and reserved to 0.

## Stage 2 — Trace one request (3–4 hours)

Read in this order:

1. `frontend/src/main.tsx`: the inventory row's form calls `action`, which calls `reserve`. The client generates a UUID and sends `POST /api/reservations`.
2. `frontend/nginx.conf`: removes the `/api/` prefix when proxying to FastAPI. In local Vite development, `vite.config.ts` does this instead.
3. `backend/app/schemas.py`: `ReserveIn` validates UUIDs and a positive integer quantity before database work starts.
4. `backend/app/main.py`: the dependency creates one SQLAlchemy session for this request. The route delegates to the service.
5. `backend/app/service.py`: `reserve` begins a transaction, locks the pickup, checks for a replay, locks the item, checks availability, updates the count, and inserts the row. `flush` sends SQL; exiting the transaction commits.
6. `backend/app/models.py` and migration `001_initial.py`: see columns, foreign keys, and constraints. The migration builds the schema; it doesn't recreate tables at every startup.
7. The route serializes the committed result. The UI refreshes its lists and counters. Another tab can be stale; the server still enforces stock at submission time.

Checkpoint: locate every step from a browser network request to the SQL statement. Explain the difference between a session, connection, transaction, flush, and commit. A SQLAlchemy session tracks Python objects; it is not a volunteer's browser session.

## Stage 3 — Break a safe toy version (3–4 hours)

Run only against the separate test database:

```sh
docker compose --profile test run --rm tests python scripts/unsafe_race.py
```

It makes its own `learning_stock` and `learning_claims` tables and resets only those toy tables. It refuses a database name without `_test`. Two separate connections both read 1; a barrier guarantees both reads finish before either writes. Each inserts a claim and writes its stale computed value 0. Result: two claims, available=0. A nonnegative check alone cannot catch overbooking.

Draw this timeline:

```text
A: BEGIN → read 1 ─── wait ─── insert claim → write 0 → COMMIT
B: BEGIN → read 1 ─── wait ───────────────── insert claim → write 0 → COMMIT
```

Transactions alone don't make a stale read safe at READ COMMITTED. Now run the application concurrency test:

```sh
docker compose --profile test run --rm tests sh -c "alembic upgrade head && pytest tests/test_concurrency.py -v"
```

Checkpoint: explain why adding FOR UPDATE to the toy read while keeping its barrier would stall: the second thread can't reach the barrier while the first holds the row lock. The real test uses events and a separate observer, not a barrier after both locked reads.

## Stage 4 — Locks, failures, and retries (3–4 hours)

Read the concurrency test. Locate the two independent TestClients, backend connection PIDs, SQLAlchemy SQL hooks, first-lock event, and `pg_blocking_pids` assertion. The hook is test-only; production code has no artificial sleep. The 5/10 second timeouts fail a stuck test; they are not performance assertions.

Predict what happens when A rolls back instead of committing: B can reserve the unit. Change the injected failure test to fail before and after the item update, then explain why persisted state stays unchanged.

Use Swagger to submit the same request key twice. Cancel it and submit that same key again. It returns the cancelled record; it does not resurrect stock allocation. Change the quantity but retain the key and predict the 409 response.

Checkpoint: explain why a network timeout does not prove rollback, and how a stored request key avoids duplication after an unknown result. Explain why UI double-click prevention alone is insufficient.

## Stage 5 — Implement cancellation independently (3–5 hours)

Follow the separate exercise before reading the finished cancellation function. Write your own implementation and run its acceptance tests. Then compare lock order, state transitions, and transaction boundaries against the completed version.

Checkpoint: pass the exercise tests and explain each line you wrote. Add a meaningful test of cancellation racing fulfillment or reservation, rather than merely checking a method was called.

## Stage 6 — Present, change, and critique (1–3 hours)

Give the five-minute demo from `DEMO.md`. Then make one modest change yourself: category filtering, a reconciliation query, or an additional failure test. Explain the effect before coding it. Support performance conclusions with reproducible measurements.


## Design review questions

1. **Why PostgreSQL?** Relational integrity, atomic transactions, and row locks fit shared finite stock. Why would SQLite not validate this particular locking behavior?
2. **What belongs in the transaction?** Both the availability decision and the counter/reservation writes. What breaks if the check is outside it?
3. **What does FOR UPDATE lock?** The selected row, until transaction completion. Ordinary readers can still read committed data. What happens to a competing writer?
4. **Is READ COMMITTED enough?** For this protocol, yes: explicit locks serialize the relevant writes. What assumptions about all mutation paths make that true?
5. **Why lock the pickup too?** It coordinates reserve/cancel/fulfill and closes the fulfilled-pickup race. Why lock multiple items in sorted order?
6. **Why not a Python mutex?** It doesn't coordinate separate workers or hosts. How does database locking avoid that limitation?
7. **How do you prove concurrency?** Separate database connections and an observed lock wait, not just two requests launched close together. Which final invariants do you assert?
8. **What does rollback undo?** The transaction's writes. Can it undo an HTTP response or an email already sent? How would external side effects change the design?
9. **Why keep idempotency keys?** A lost response leaves the commit outcome unknown. Why must retries use the same key and payload?
10. **What if two requests reuse a key with different payloads?** Conflict, with no extra stock change. Why is the database UNIQUE constraint still necessary?
11. **How are repeated cancellation and fulfillment safe?** Terminal state is checked under the pickup lock before counter changes. Why is “increment available on every cancel” wrong?
12. **Could a conditional UPDATE replace SELECT FOR UPDATE?** Yes, with an availability predicate and RETURNING, in the same transaction as the insert. Compare clarity and round trips without inventing benchmarks.
13. **What could become a bottleneck?** A popular item serializes writers; long transactions prolong waits. How would you measure this before redesigning?
14. **What's missing for a real deployment?** Authentication, authorization, reconciliation/audit history, monitoring, backups, and requirements from actual users. Which would you prioritize and why?
15. **What did you personally learn or change?** Show your independent cancellation implementation and a test you wrote; be candid about assistance used.

Ready means you can trace, predict, reproduce, explain, and modify the system without memorized wording.
