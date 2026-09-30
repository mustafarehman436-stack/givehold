"""Initial inventory and pickup schema."""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def upgrade():
    op.create_table(
        "items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("condition", sa.String(40), nullable=False),
        sa.Column("on_hand", sa.Integer, nullable=False),
        sa.Column("reserved", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint(
            "on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand", name="valid_stock"
        ),
    )
    op.create_table(
        "volunteers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
    )
    op.create_table(
        "pickups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "volunteer_id", sa.Integer, sa.ForeignKey("volunteers.id"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('open', 'fulfilled')", name="pickup_state"),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_key", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "pickup_id", sa.String(36), sa.ForeignKey("pickups.id"), nullable=False
        ),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("items.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled', 'collected')", name="reservation_state"
        ),
    )
    op.create_index("ix_reservations_pickup_id", "reservations", ["pickup_id"])
    op.create_index("ix_reservations_item_id", "reservations", ["item_id"])


def downgrade():
    for table in ["reservations", "pickups", "volunteers", "items"]:
        op.drop_table(table)
