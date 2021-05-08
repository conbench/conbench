"""add distribution

Revision ID: b7ffcaaeb240
Revises: 8411faeebc1f
Create Date: 2021-05-03 15:13:40.733836

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7ffcaaeb240"
down_revision = "8411faeebc1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "distribution",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("sha", sa.String(length=50), nullable=False),
        sa.Column("case_id", sa.String(length=50), nullable=False),
        sa.Column("context_id", sa.String(length=50), nullable=False),
        sa.Column("machine_id", sa.String(length=50), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("mean_mean", sa.Numeric(), nullable=True),
        sa.Column("mean_sd", sa.Numeric(), nullable=True),
        sa.Column("min_mean", sa.Numeric(), nullable=True),
        sa.Column("min_sd", sa.Numeric(), nullable=True),
        sa.Column("max_mean", sa.Numeric(), nullable=True),
        sa.Column("max_sd", sa.Numeric(), nullable=True),
        sa.Column("median_mean", sa.Numeric(), nullable=True),
        sa.Column("median_sd", sa.Numeric(), nullable=True),
        sa.Column("first_timestamp", sa.DateTime(), nullable=False),
        sa.Column("last_timestamp", sa.DateTime(), nullable=False),
        sa.Column("observations", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_id"], ["context.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "distribution_case_id_index", "distribution", ["case_id"], unique=False
    )
    op.create_index(
        "distribution_context_id_index", "distribution", ["context_id"], unique=False
    )
    op.create_index(
        "distribution_index",
        "distribution",
        ["sha", "case_id", "context_id", "machine_id"],
        unique=True,
    )
    op.create_index(
        "distribution_machine_id_index", "distribution", ["machine_id"], unique=False
    )
    op.create_index("distribution_sha_index", "distribution", ["sha"], unique=False)


def downgrade():
    op.drop_index("distribution_sha_index", table_name="distribution")
    op.drop_index("distribution_machine_id_index", table_name="distribution")
    op.drop_index("distribution_index", table_name="distribution")
    op.drop_index("distribution_context_id_index", table_name="distribution")
    op.drop_index("distribution_case_id_index", table_name="distribution")
    op.drop_table("distribution")
