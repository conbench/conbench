"""api_token

Adds the api_token table for the Go backend's user-attributed write
authentication (rewrite Phase 4, Leaf 3a). The legacy app never reads it.
Timestamps follow the house naive-UTC convention. token_prefix is stored at
mint time because it cannot be recovered from token_hash afterwards.

Revision ID: b7e4a90c2d15
Revises: 99895af5dae2
Create Date: 2026-06-12 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7e4a90c2d15"
down_revision = "99895af5dae2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_token",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_prefix", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade():
    op.drop_table("api_token")
