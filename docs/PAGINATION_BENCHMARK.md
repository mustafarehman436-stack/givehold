# Inventory pagination comparison

Measured September 30, 2026 on Windows 11, Python 3.12.14 and PostgreSQL 16.8. This compares the original full-list inventory handler against the new first-page inventory handler on the same 10,000-item database.

| Measurement | Original full list | First page with totals |
|---|---:|---:|
| Returned item rows | 10,000 | 50 |
| Median request latency (median of runs) | 181.03 ms | 4.55 ms |
| p95 request latency (median of runs) | 211.85 ms | 5.72 ms |
| Response body | 1,117,789 bytes | 5,456 bytes |

The median of run-level p95 latencies fell by **97.3%**. This measures first-page retrieval by returning fewer rows, not a faster full export or a 97% improvement across the whole app.

## Method

Five runs per handler, 50 serial requests per run (250 measured requests each), after five warmups per handler. Order alternates between runs. Both execute in the same Python process through FastAPI TestClient against local PostgreSQL. The baseline is an exact copy of the previous list handler retained only in the benchmark script. The new endpoint includes a filtered count and whole-inventory quantity totals. The benchmark checks that its first 50 items equal the first 50 baseline rows and that totals match. No network, TLS, browser rendering, other list endpoints, or hosted-service latency is measured. No CPU/memory profiling was performed. Background OS activity is uncontrolled.

Original run-level p95 range: 197.29–230.38 ms. Paginated range: 5.05–5.85 ms. [Raw results](pagination-results.json).

## Change and tradeoffs

The interface requests 50 items at a time and uses Previous/Next navigation. Search runs on the server across all items. Totals cover the full inventory, regardless of page or search. Reservation responses include item names so paging does not remove names from history. Refresh no longer requests all four resources twice.

The API also caps `/items` at 100 rows (default 50); clients retrieving all items must iterate with `offset` and `limit`. `/inventory` accepts those same parameters plus `q` and returns `items`, matched `total`, and global `on_hand`, `reserved`, `available` counts. Search is case-insensitive substring matching with literal wildcard escaping.

Offset pagination is intentionally simple; deep offsets and substring search still need separate measurement at larger scales. Counts and totals scan records. Under concurrent writes, rows and aggregate totals can reflect different committed snapshots; refresh reconciles the display. Reservation stock checks remain transactional. Pickup and reservation lists remain unpaginated and can become a separate bottleneck.

## Verification and reproduction

29 PostgreSQL tests pass, covering stock locking, cancellation, fulfillment, rollback, pagination boundaries, search, input validation, global totals, and history names. TypeScript checking and the frontend build pass. Browser checks covered next/last-page navigation, search for an item beyond page one, reservation, and cancellation.

**Destructive test-only command:** the script clears its target database before and after the run. It refuses database names without `_test`. Use an isolated migrated test database; do not run tests or another benchmark against it concurrently.

```sh
docker compose --profile test run --rm tests sh -c "alembic upgrade head && python scripts/benchmark_pagination.py"
```

The recorded run used native Python/PostgreSQL, not Docker. For that setup, set `DATABASE_URL` to the disposable database, set `PYTHONPATH` to the backend directory, and run `python scripts/benchmark_pagination.py` from the backend directory.
