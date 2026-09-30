from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(
            "on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand", name="valid_stock"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(60))
    condition: Mapped[str] = mapped_column(String(40))
    on_hand: Mapped[int]
    reserved: Mapped[int] = mapped_column(default=0, server_default="0")


class Volunteer(Base):
    __tablename__ = "volunteers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class Pickup(Base):
    __tablename__ = "pickups"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'fulfilled')", name="pickup_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id"))
    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint(
            "status IN ('active', 'cancelled', 'collected')", name="reservation_state"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    pickup_id: Mapped[str] = mapped_column(ForeignKey("pickups.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
