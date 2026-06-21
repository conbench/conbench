"""alert_delivery_outbox

Revision ID: f6d4a3b2c1e0
Revises: 7df65e9a0c12
Create Date: 2026-06-19 00:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6d4a3b2c1e0"
down_revision = "7df65e9a0c12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_delivery",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="alert_delivery_status_check",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["alert_event.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "channel",
            "target",
            name="alert_delivery_event_channel_target_key",
        ),
    )
    op.create_index("alert_delivery_event_id_index", "alert_delivery", ["event_id"])
    op.execute(
        "CREATE INDEX alert_delivery_channel_status_next_attempt_index "
        "ON alert_delivery (channel, status, next_attempt_at, created_at, id)"
    )


def downgrade() -> None:
    op.drop_index("alert_delivery_channel_status_next_attempt_index", table_name="alert_delivery")
    op.drop_index("alert_delivery_event_id_index", table_name="alert_delivery")
    op.drop_table("alert_delivery")
