# Local benchmarks

Measured September 30, 2026. Python 3.12.14, PostgreSQL 16.8, Windows 11.

23 PostgreSQL tests passed in 1.66 seconds, including the deterministic lock-wait test, cancellation, fulfillment, validation, and rollback. TypeScript checking and the production frontend build passed. The JS bundle is 196.40 kB (61.69 kB gzip); CSS is 5.75 kB (1.97 kB gzip).

## Method

Three runs per scenario, 200 requests per run. FastAPI TestClient executes real API handlers against local PostgreSQL; there is no network server, TLS, browser, or Render/Neon latency. Each run resets the disposable database, creates 200 separate pickups, and warms the read route with 10 requests. The inventory contains three items. Reservation workloads target one item with separate pickup IDs, so item locking is shared while pickup locking is not. Eight worker threads issue up to eight requests concurrently. Setup is outside the timed interval; executor overhead is included in throughput. Per-request latency starts when its worker runs, excluding executor queue time.

| Scenario | Workers | Median latency, ms (median of runs) | p95 latency range, ms | Requests/s range |
|---|---:|---:|---:|---:|
| inventory_read | 1 | 1.78 | 1.94–2.40 | 489.7–605.3 |
| reserve | 1 | 3.74 | 4.14–5.25 | 233.0–287.8 |
| reserve_contended | 8 | 19.94 | 42.13–51.38 | 309.5–327.6 |
| last_unit | 8 | 17.34 | 23.86–71.52 | 349.9–395.6 |

All stocked reservation requests succeeded. In each last-unit run, exactly one request succeeded and 199 returned 409. Every run checked that reserved stock matched active reservation quantities. The separate concurrency test proves an actual PostgreSQL lock wait; this benchmark is not that proof.

## Interpretation

These are small-dataset local measurements, not production capacity or a scalability claim. The last-unit throughput includes rejected requests. Shared-item contention increases latency; different items, larger lists, cold starts, network latency, and multiple server workers need separate measurement. There is no CPU or memory profiling in this run. Inventory and history endpoints are unpaginated, so their cost grows with record count.

## Reproduce

The benchmark **clears all records in its target database** and refuses a non-PostgreSQL database or a name without `_test`. Use only a disposable test database and do not run pytest against it simultaneously.

```sh
docker compose --profile test run --rm tests sh -c "alembic upgrade head && python scripts/benchmark.py"
```

Or set `DATABASE_URL` to a disposable migrated PostgreSQL database ending in `_test`, set `PYTHONPATH` to the backend directory, and run `python scripts/benchmark.py` from that directory. The recorded results used this native setup, not Docker. See [raw results](benchmark-results.json).
