"""alert_rules

Revision ID: c4f9e2a1d6b8
Revises: b7e4a90c2d15
Create Date: 2026-06-17 23:58:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c4f9e2a1d6b8"
down_revision = "b7e4a90c2d15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rule",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("repository", sa.Text(), nullable=False),
        sa.Column("baseline", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("threshold_z", sa.Float(), nullable=False),
        sa.Column("run_reason", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("state", sa.Text(), nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("alert_rule_user_id_index", "alert_rule", ["user_id"])
    op.create_index(
        "alert_rule_enabled_repository_index",
        "alert_rule",
        ["enabled", "repository"],
    )

    op.create_table(
        "alert_event",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("rule_id", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("commit_sha", sa.Text(), nullable=True),
        sa.Column("report_url", sa.Text(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rule.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX alert_event_rule_created_index "
        "ON alert_event (rule_id, created_at DESC, id DESC)"
    )


def downgrade() -> None:
    op.drop_index("alert_event_rule_created_index", table_name="alert_event")
    op.drop_table("alert_event")
    op.drop_index("alert_rule_enabled_repository_index", table_name="alert_rule")
    op.drop_index("alert_rule_user_id_index", table_name="alert_rule")
    op.drop_table("alert_rule")
