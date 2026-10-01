"""Local API microbenchmark. Resets only a disposable *_test PostgreSQL database."""
import json
import math
import platform
import statistics
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.db import engine
from app.main import app
from app.seed import seed


def reset():
    assert engine.dialect.name == 'postgresql' and engine.url.database.endswith('_test')
    with engine.begin() as db:
        db.execute(text('TRUNCATE reservations, pickups, items, volunteers RESTART IDENTITY CASCADE'))
    seed()


def run():
    results = []
    for repeat in range(3):
        for scenario, workers in [('inventory_read', 1), ('reserve', 1), ('reserve_contended', 8), ('last_unit', 8)]:
            reset()
            count = 200
            with engine.begin() as db:
                db.execute(text('UPDATE items SET on_hand=:n WHERE id=1'), {'n': 1 if scenario == 'last_unit' else count})
                pickups = [str(uuid4()) for _ in range(count)]
                db.execute(text("INSERT INTO pickups (id, volunteer_id) VALUES (:id, 1)"), [{'id': p} for p in pickups])
            with TestClient(app) as client:
                for _ in range(10):
                    assert client.get('/items').status_code == 200
                def request(i):
                    start = perf_counter()
                    if scenario == 'inventory_read':
                        response = client.get('/items')
                    else:
                        response = client.post('/reservations', json={'request_key': str(uuid4()), 'pickup_id': pickups[i], 'item_id': 1, 'quantity': 1})
                    return (perf_counter()-start)*1000, response.status_code
                start = perf_counter()
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    responses = list(pool.map(request, range(count)))
                elapsed = perf_counter()-start
            latencies = sorted(t for t, _ in responses)
            statuses = {str(code): sum(c == code for _, c in responses) for code in {c for _, c in responses}}
            expected = {'200': 1, '409': count-1} if scenario == 'last_unit' else {'200': count}
            assert statuses == expected, statuses
            with engine.connect() as db:
                reserved, active = db.execute(text("SELECT reserved, (SELECT COALESCE(SUM(quantity),0) FROM reservations WHERE status='active' AND item_id=1) FROM items WHERE id=1")).one()
                assert reserved == active == (0 if scenario == 'inventory_read' else 1 if scenario == 'last_unit' else count)
            results.append(dict(scenario=scenario, repeat=repeat+1, requests=count, workers=workers, median_ms=round(statistics.median(latencies),2), p95_ms=round(latencies[math.ceil(count*.95)-1],2), requests_per_second=round(count/elapsed,1), statuses=statuses))
    with engine.connect() as db:
        pg = db.scalar(text('SHOW server_version'))
    print('BENCHMARK_JSON='+json.dumps({'python': platform.python_version(), 'os': platform.platform(), 'postgresql': pg, 'results': results}))
    reset()


if __name__ == '__main__':
    run()
