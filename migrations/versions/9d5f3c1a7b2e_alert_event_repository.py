"""alert_event_repository

Revision ID: 9d5f3c1a7b2e
Revises: f6d4a3b2c1e0
Create Date: 2026-06-19 03:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "9d5f3c1a7b2e"
down_revision = "f6d4a3b2c1e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_event", sa.Column("repository", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE alert_event AS e
        SET repository = r.repository
        FROM alert_rule AS r
        WHERE r.id = e.rule_id
        """
    )
    op.alter_column(
        "alert_event",
        "repository",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("alert_event", "repository")
