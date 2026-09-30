from uuid import UUID
from sqlalchemy import select
from .db import Session
from .models import Item, Volunteer, Pickup


def seed():
    with Session.begin() as db:
        if db.scalar(select(Volunteer.id).limit(1)) is not None:
            print("Seed skipped: volunteers already exist.")
            return
        db.add_all(
            [Volunteer(id=1, name="Alex River"), Volunteer(id=2, name="Sam Meadow")]
        )
        db.flush()
        db.add_all(
            [
                Item(
                    name="Winter blanket",
                    category="Bedding",
                    condition="new",
                    on_hand=1,
                ),
                Item(
                    name="Kitchen starter kit",
                    category="Household",
                    condition="good",
                    on_hand=8,
                ),
                Item(
                    name="Warm coat", category="Clothing", condition="good", on_hand=12
                ),
            ]
        )
        db.add_all(
            [
                Pickup(id=str(UUID(int=1)), volunteer_id=1),
                Pickup(id=str(UUID(int=2)), volunteer_id=2),
            ]
        )
    print("Fictional data ready.")


if __name__ == "__main__":
    seed()
