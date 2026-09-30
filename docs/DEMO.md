# Five-minute demonstration

Start: `docker compose up --build -d --wait`. Use only the fictional data.

**0:00 — Problem.** “Volunteering at a donation-based charity inspired GiveHold. The question is what happens if two volunteers reserve the last blanket simultaneously.”

**0:30 — Two browser sessions.** Open localhost:8080 in two tabs. Select Alex in one and Sam in the other. Each has an open pickup. Refresh both before reserving so both see the one available blanket. Submit in Alex's tab, then submit from Sam's stale tab. Alex succeeds; Sam sees an out-of-stock conflict. This demonstrates handling stale UI, not proof that transactions overlapped.

If the seed blanket was already used, create a new one-unit item first or use the automated script below. Don't reset a database merely for the presentation.

**1:30 — Actual competing requests.** Run:

```sh
docker compose exec api python scripts/demo_race.py
```

This creates a fresh demo item and two pickup IDs, sends requests from separate HTTP sessions, and asserts one success, one 409, exactly one reservation, and (on_hand,reserved,available)=(1,1,0). Either volunteer may win. This script launches simultaneous requests; the automated integration test separately proves lock overlap deterministically.

**2:30 — Prove overlap.** Run the PostgreSQL test suite. Explain the `pg_blocking_pids` check in `tests/test_concurrency.py`: the second backend really waits for the first backend's lock before release. Show the final inventory and reservation assertions.

**3:30 — Complete the workflow.** Cancel the winner's reservation and watch availability return. Reserve again, mark the pickup collected, and show its timestamp and collected history. Explain why repeat cancellation doesn't add stock and repeat fulfillment doesn't subtract it twice.

**4:30 — Tradeoffs.** Show the transaction in `service.py` and the schema. Explain the demo volunteer selector is not authentication; a real deployment needs access control. Describe one feature you deliberately omitted to keep the correctness story understandable.

End by answering: “What happens if the database commits but the response is lost?” Demonstrate replaying the same request key through Swagger: it returns the original reservation.
