"""Drop data and time tables

Revision ID: 4fb49a9299a2
Revises: 88040ddc0b08
Create Date: 2022-03-31 12:22:00.821391

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4fb49a9299a2"
down_revision = "88040ddc0b08"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("data")
    op.drop_table("time")


def downgrade():
    op.create_table(
        "time",
        sa.Column("id", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column(
            "summary_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column("iteration", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("result", sa.NUMERIC(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["summary_id"],
            ["summary.id"],
            name="time_summary_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="time_pkey"),
    )
    op.create_index("time_summary_id_index", "time", ["summary_id"], unique=False)
    op.create_table(
        "data",
        sa.Column("id", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column(
            "summary_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column("iteration", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("result", sa.NUMERIC(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["summary_id"],
            ["summary.id"],
            name="data_summary_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="data_pkey"),
    )
    op.create_index("data_summary_id_index", "data", ["summary_id"], unique=False)
