"""Intentionally broken learning exercise in a disposable *_test database only.

Uses its own tables so the demonstration can violate the cross-table invariant
without weakening any GiveHold application constraint.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import create_engine, text


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    if engine.dialect.name != "postgresql" or not engine.url.database.endswith("_test"):
        raise SystemExit(
            "Refusing: use a disposable PostgreSQL database ending in _test"
        )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS learning_stock (id integer PRIMARY KEY, available integer NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS learning_claims (volunteer integer PRIMARY KEY)"
            )
        )
        conn.execute(text("TRUNCATE learning_stock, learning_claims"))
        conn.execute(text("INSERT INTO learning_stock VALUES (1,1)"))
    barrier = Barrier(2)

    def unsafe(volunteer):
        with engine.begin() as conn:
            available = conn.scalar(
                text("SELECT available FROM learning_stock WHERE id=1")
            )
            print(f"Volunteer {volunteer} read available={available}")
            barrier.wait(timeout=5)  # Both read 1 before either writes.
            if available >= 1:
                conn.execute(
                    text("INSERT INTO learning_claims VALUES (:volunteer)"),
                    {"volunteer": volunteer},
                )
                conn.execute(
                    text("UPDATE learning_stock SET available=:remaining WHERE id=1"),
                    {"remaining": available - 1},
                )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(unsafe, [1, 2]))
    with engine.connect() as conn:
        print("Claims:", conn.scalar(text("SELECT count(*) FROM learning_claims")))
        print("Available:", conn.scalar(text("SELECT available FROM learning_stock")))
    print("BUG: two claims for one unit, although available is not negative.")
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE learning_claims, learning_stock'))
    print('Removed the two temporary learning tables.')
    print(
        "Now run pytest tests/test_concurrency.py -v to observe the protected implementation."
    )


if __name__ == "__main__":
    main()
