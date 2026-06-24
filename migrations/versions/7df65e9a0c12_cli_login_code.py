"""cli_login_code

Adds a shared one-time code table for CLI loopback login. The plaintext code is
shown only to the CLI callback; the database stores only a SHA-256 hash, a user
id, and short expiry/redeem timestamps so multi-replica deployments do not
depend on process-local memory or sticky routing.

Revision ID: 7df65e9a0c12
Revises: c4f9e2a1d6b8
Create Date: 2026-06-18 14:10:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = "7df65e9a0c12"
down_revision = "c4f9e2a1d6b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cli_login_code",
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("code_hash"),
    )
    op.create_index(
        "cli_login_code_expires_at_index",
        "cli_login_code",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("cli_login_code_expires_at_index", table_name="cli_login_code")
    op.drop_table("cli_login_code")
