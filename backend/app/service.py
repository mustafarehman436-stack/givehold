"""All mutations own one transaction. Lock order: pickup, then items by ID."""

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import Item, Pickup, Reservation, Volunteer


def fail(status, message):
    raise HTTPException(status, message)


def locked_pickup(db, pickup_id):
    pickup = db.scalar(select(Pickup).where(Pickup.id == pickup_id).with_for_update())
    if pickup is None:
        fail(404, "Pickup not found")
    return pickup


def create_pickup(db, data):
    with db.begin():
        # Serialize repeated creation for this volunteer before inspecting the ID.
        if (
            db.scalar(
                select(Volunteer)
                .where(Volunteer.id == data.volunteer_id)
                .with_for_update()
            )
            is None
        ):
            fail(404, "Volunteer not found")
        existing = db.get(Pickup, str(data.id))
        if existing:
            if existing.volunteer_id != data.volunteer_id:
                fail(409, "Pickup ID already belongs to another volunteer")
            return existing
        pickup = Pickup(id=str(data.id), volunteer_id=data.volunteer_id)
        db.add(pickup)
        db.flush()
        return pickup


def reserve(db, data):
    with db.begin():
        pickup = locked_pickup(db, str(data.pickup_id))
        existing = db.scalar(
            select(Reservation).where(Reservation.request_key == str(data.request_key))
        )
        if existing:
            if (existing.pickup_id, existing.item_id, existing.quantity) != (
                str(data.pickup_id),
                data.item_id,
                data.quantity,
            ):
                fail(409, "Request key reused with different input")
            return existing
        if pickup.status != "open":
            fail(409, "Pickup already fulfilled")
        item = db.scalar(select(Item).where(Item.id == data.item_id).with_for_update())
        if item is None:
            fail(404, "Item not found")
        if item.on_hand - item.reserved < data.quantity:
            fail(409, "Not enough available stock")
        item.reserved += data.quantity
        reservation = Reservation(
            request_key=str(data.request_key),
            pickup_id=pickup.id,
            item_id=item.id,
            quantity=data.quantity,
        )
        db.add(reservation)
        db.flush()  # A failure here rolls back the counter too.
        return reservation


def cancel(db, reservation_id):
    with db.begin():
        # Read only the immutable pickup ID before taking the parent lock.
        pickup_id = db.scalar(
            select(Reservation.pickup_id).where(Reservation.id == reservation_id)
        )
        if pickup_id is None:
            fail(404, "Reservation not found")
        locked_pickup(db, pickup_id)
        reservation = db.get(Reservation, reservation_id)
        if reservation.status == "cancelled":
            return reservation
        if reservation.status == "collected":
            fail(409, "Collected reservations cannot be cancelled")
        item = db.scalar(
            select(Item).where(Item.id == reservation.item_id).with_for_update()
        )
        item.reserved -= reservation.quantity
        reservation.status = "cancelled"
        reservation.updated_at = datetime.now(timezone.utc)
        db.flush()
        return reservation


def fulfill(db, pickup_id):
    with db.begin():
        pickup = locked_pickup(db, pickup_id)
        if pickup.status == "fulfilled":
            return pickup
        reservations = list(
            db.scalars(
                select(Reservation).where(
                    Reservation.pickup_id == pickup_id, Reservation.status == "active"
                )
            )
        )
        if not reservations:
            fail(409, "Pickup has no active reservations")
        ids = sorted({r.item_id for r in reservations})
        items = {
            i.id: i
            for i in db.scalars(
                select(Item).where(Item.id.in_(ids)).order_by(Item.id).with_for_update()
            )
        }
        now = datetime.now(timezone.utc)
        for reservation in reservations:
            item = items[reservation.item_id]
            item.reserved -= reservation.quantity
            item.on_hand -= reservation.quantity
            reservation.status = "collected"
            reservation.updated_at = now
        pickup.status = "fulfilled"
        pickup.fulfilled_at = now
        db.flush()
        return pickup
