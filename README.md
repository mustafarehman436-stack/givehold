# GiveHold

Donation inventory and pickup reservations.

Built from my experience volunteering at a donation-based charity. Volunteers can track stock, reserve items, and record pickups. PostgreSQL transactions and row locks prevent competing reservations from claiming the same stock.

[Live demo](https://shelterstock-demo.onrender.com) · The first load may take about a minute.

This prototype uses fictional data.

## Run locally

Install Docker Desktop (or Docker Engine with Compose v2), then run from this directory:

```sh
docker compose up --build -d --wait
```

Open **http://localhost:8080**. API documentation: **http://localhost:8000/docs**. The API runs Alembic migrations and inserts fictional data on first startup. Alex River and Sam Meadow each start with an open pickup. There is one winter blanket.

```sh
docker compose logs api
docker compose down
```

`down` preserves the named database volume. `docker compose down -v` deletes this project's local data: use only when you intentionally want a fresh demo. Seed data is skipped once volunteers exist. Don't run multiple seed processes concurrently.

## Try the core workflow

1. Select Alex River and an open pickup on Inventory. Reserve one blanket.
2. Switch to Sam Meadow. The blanket now has zero available; refresh another tab if necessary.
3. In Alex's Reservations screen, cancel. The unit becomes available again.
4. Reserve again with Sam, then open Pickups and mark it collected.
5. Review the collected reservation and pickup timestamp. On hand and reserved are both zero.

Use **Add item** for a new item type; **Edit** changes its description and physical count. Setting a count below already reserved stock returns a conflict. There is no destructive delete: keeping records preserves pickup history.

## Tests and demonstration

```sh
docker compose --profile test up --build --abort-on-container-exit --exit-code-from tests tests
docker compose exec api python scripts/demo_race.py
```

Tests use a separate PostgreSQL database in a separate container, not SQLite or mocked locks. Test fixtures refuse to truncate a database whose name does not end in `_test`. The demo creates a fresh one-unit item and two pickups each run; it does not erase existing data.

The concurrency test pauses the first request after PostgreSQL grants its item row lock, starts the second request on another connection, and queries `pg_blocking_pids` to prove that the second is waiting for the first. Only then does it release the first. It checks HTTP 200 + 409, the out-of-stock message, exactly one reservation, and consistent stock. Merely launching two threads would not prove overlap.

Other tests cover cancellation/replay, fulfillment/replay, invalid quantities, stock constraints, pickup ID reuse, multi-item fulfillment, and rollback after a forced reservation insert failure. The intentionally unfinished exercise is excluded from the normal test suite.

## Small architecture

```text
React + TypeScript → nginx /api proxy → FastAPI → SQLAlchemy → PostgreSQL
                                            └─ service.py owns transactions
```

The frontend has three views in one React component. FastAPI routes validate input and serialize results; `service.py` contains workflow rules. There is no queue, cache, distributed lock, or separate repository layer. PostgreSQL is the shared source of truth across processes.

| Table | Role | Relationships |
|---|---|---|
| items | Description, category, condition, on-hand and reserved counts | One item has many reservations |
| volunteers | Fictional names used as demo sessions | One volunteer has many pickups |
| pickups | Open or fulfilled collection; timestamps | Belongs to one volunteer; has many reservations |
| reservations | Item quantity, lifecycle state, unique request key | Belongs to one pickup and one item |

Quantities are whole units of interchangeable items with the same description/condition. `on_hand` includes units set aside. `reserved` counts active reservations; `available = on_hand - reserved`. Database checks require `0 <= reserved <= on_hand` and positive reservation quantities. The stronger cross-table invariant is `items.reserved = SUM(active reservations.quantity)`; the service maintains this in transactions. A SQL check constraint cannot enforce that aggregate across tables.

| Operation | On hand | Reserved | Reservation state |
|---|---:|---:|---|
| Reserve q | unchanged | +q | active |
| Cancel q | unchanged | -q | cancelled |
| Collect q | -q | -q | collected |

Reservations have only `active → cancelled` or `active → collected` transitions. Terminal records remain as history. A pickup becomes fulfilled atomically with all its active reservations; an empty pickup cannot be fulfilled. Cancelling every reservation leaves an open pickup that can be reused.

## Why the last unit cannot be booked twice

At PostgreSQL's default READ COMMITTED isolation, the service starts a transaction, locks the pickup, and selects the item **FOR UPDATE**. It checks availability while holding that lock, updates the reserved counter, inserts the reservation, and commits. A competing transaction waits for the same item row. After the winner commits, it reads the new counter and receives **409 Conflict** when stock is exhausted. Locks last until commit or rollback.

All pickup mutations acquire the pickup lock first. Fulfillment locks multiple items in ascending ID order to reduce deadlock risk. Item edits lock only their item; they never acquire a pickup lock afterward. This protocol also prevents cancellation, fulfillment, and a new reservation from modifying one pickup simultaneously. It is valid only while every stock-writing path follows these rules.

See [PostgreSQL row locking](https://www.postgresql.org/docs/16/explicit-locking.html) and [READ COMMITTED](https://www.postgresql.org/docs/16/transaction-iso.html). An in-process Python lock would not coordinate multiple API workers. An atomic conditional UPDATE is another valid approach; explicit row locks make the check-and-write sequence easier to trace here.

## Repeated submissions and failures

- A reservation request includes a client-generated UUID `request_key`, stored with a UNIQUE constraint. The same key and same payload return the existing reservation, including a cancelled or collected state. Reusing a key for different input returns 409. Start a new intentional reservation with a new key.
- The UI disables concurrent submissions and retains uncertain reservation and pickup keys in per-tab session storage, including across refreshes. A returned validation/conflict error clears the key. Server errors or a lost response retain it. Retry with the same pickup, item, and quantity. Closing the tab clears session storage; inspect persisted records before submitting again from a new tab. API clients must likewise retain the key until they know the result. Separate successful clicks are new intentional reservations, not retries.
- Requests for the same pickup serialize on its lock. Concurrent reuse of a key across different pickups is caught by the database uniqueness constraint; the losing transaction rolls back and returns 409.
- Pickup creation uses a caller-generated UUID as its idempotency key. Repeating the same ID/volunteer returns the existing pickup; changing the volunteer conflicts.
- Cancellation and fulfillment inspect persisted lifecycle state. Repeating the same terminal operation returns success without another stock adjustment. Cancelling a collected reservation returns 409.
- Item creation is not idempotent: it creates a new item type. The UI blocks double clicks but does not automatically retry; after an uncertain create result, refresh and check before creating again. Item edits set an absolute count, rather than adding a donation increment.
- `with db.begin()` rolls back both the stock update and reservation insert if either fails. A successful database commit followed by a lost HTTP response is different from a rollback; the request key resolves that uncertainty. Idempotency keys are retained with reservation history, with no expiry in this prototype.

## API overview

| Method / path | Meaning |
|---|---|
| GET /health | Database connectivity |
| GET, POST /items | List inventory / create item type |
| PUT /items/{id} | Replace metadata and physical count |
| GET /volunteers | Fictional session choices |
| GET, POST /pickups | List / create pickup with UUID and volunteer ID |
| GET, POST /reservations | List / reserve using UUID request key |
| POST /reservations/{id}/cancel | Release active reservation |
| POST /pickups/{uuid}/fulfill | Collect all active reservations atomically |

Success: 200 (201 for item creation). Invalid input: 422. Missing resource: 404. Insufficient stock, invalid state, or conflicting key: 409. Swagger documents request schemas. Quantities are strict integers; strings, booleans, and fractions are rejected.

## Learn and explain it

- [Learning stages, code trace, and design questions](docs/LEARNING_GUIDE.md)
- [Implement cancellation yourself](docs/CANCELLATION_EXERCISE.md)
- [Two-session presentation script](docs/DEMO.md)
- [Deployment and GitHub publishing](docs/DEPLOYMENT.md)
- [Free hosting on Render and Neon](docs/FREE_DEMO.md)
- [Verification record](docs/VERIFICATION.md)

## Scope and tradeoffs

The local Compose app has no authentication or authorization: the volunteer dropdown is a demo session selector, not a security boundary. Compose binds HTTP ports to localhost and does not publish the database port. The hosted demo is also public, with shared fictional records and no sign-in; see the free demo instructions. Use with real data requires individual authorization, HTTPS, secret management, request limits, and backups.

Inventory edits are authoritative counts with last-write-wins behavior; an audit ledger and optimistic version checking would improve real inventory reconciliation. History records current item names rather than immutable name snapshots. Lists are unpaginated. There is no automatic reservation expiry, partial fulfillment, family data, multi-location stock, or multi-organization support.

## Benchmarks

See [local measurements and methodology](docs/BENCHMARKS.md).
