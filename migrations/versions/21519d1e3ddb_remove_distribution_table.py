"""remove Distribution table

Revision ID: 21519d1e3ddb
Revises: bb4953386fe1
Create Date: 2023-01-30 12:34:45.732948

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "21519d1e3ddb"
down_revision = "bb4953386fe1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("distribution_commit_hardware_index", table_name="distribution")
    op.drop_index("distribution_index", table_name="distribution")
    op.drop_table("distribution")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "distribution",
        sa.Column("id", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column(
            "case_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column(
            "context_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column(
            "hardware_hash", sa.VARCHAR(length=250), autoincrement=False, nullable=False
        ),
        sa.Column("unit", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("mean_mean", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("mean_sd", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("min_mean", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("min_sd", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("max_mean", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("max_sd", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("median_mean", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("median_sd", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column(
            "first_timestamp",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "last_timestamp",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("observations", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("limit", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "commit_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name="distribution_case_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commit_id"],
            ["commit.id"],
            name="distribution_commit_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["context_id"],
            ["context.id"],
            name="distribution_context_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="distribution_pkey"),
    )
    op.create_index(
        "distribution_index",
        "distribution",
        ["case_id", "context_id", "commit_id", "hardware_hash"],
        unique=False,
    )
    op.create_index(
        "distribution_commit_hardware_index",
        "distribution",
        ["commit_id", "hardware_hash"],
        unique=False,
    )
    # ### end Alembic commands ###
