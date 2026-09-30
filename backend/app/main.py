from uuid import UUID
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from .db import Session
from .models import Item, Volunteer, Pickup, Reservation
from .schemas import ItemIn, PickupIn, ReserveIn
from . import service

app = FastAPI(title="GiveHold", version="1.0.0")


def database():
    with Session() as db:
        yield db


def record(obj):
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    if isinstance(obj, Item):
        data["available"] = obj.on_hand - obj.reserved
    return data


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Conflicting request or database constraint; refresh and retry with the same request key."
        },
    )


@app.get("/health")
def health(db=Depends(database)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/items")
def items(db=Depends(database)):
    return [record(x) for x in db.scalars(select(Item).order_by(Item.id))]


@app.post("/items", status_code=201)
def create_item(data: ItemIn, db=Depends(database)):
    with db.begin():
        item = Item(**data.model_dump())
        db.add(item)
        db.flush()
    return record(item)


@app.put("/items/{item_id}")
def update_item(item_id: int, data: ItemIn, db=Depends(database)):
    with db.begin():
        item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
        if item is None:
            service.fail(404, "Item not found")
        if data.on_hand < item.reserved:
            service.fail(409, "On-hand quantity cannot be below reserved quantity")
        for key, value in data.model_dump().items():
            setattr(item, key, value)
        db.flush()
    return record(item)


@app.get("/volunteers")
def volunteers(db=Depends(database)):
    return [record(x) for x in db.scalars(select(Volunteer).order_by(Volunteer.id))]


@app.get("/pickups")
def pickups(db=Depends(database)):
    return [
        record(x) for x in db.scalars(select(Pickup).order_by(Pickup.created_at.desc()))
    ]


@app.post("/pickups")
def create_pickup(data: PickupIn, db=Depends(database)):
    return record(service.create_pickup(db, data))


@app.get("/reservations")
def reservations(db=Depends(database)):
    return [
        record(x)
        for x in db.scalars(select(Reservation).order_by(Reservation.id.desc()))
    ]


@app.post("/reservations")
def reserve(data: ReserveIn, db=Depends(database)):
    return record(service.reserve(db, data))


@app.post("/reservations/{reservation_id}/cancel")
def cancel(reservation_id: int, db=Depends(database)):
    return record(service.cancel(db, reservation_id))


@app.post("/pickups/{pickup_id}/fulfill")
def fulfill(pickup_id: UUID, db=Depends(database)):
    return record(service.fulfill(db, str(pickup_id)))
