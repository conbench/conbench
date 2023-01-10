"""add is_step_change, fix branch limit

Revision ID: 498ade3999dd
Revises: 4d8d67396f79
Create Date: 2023-01-10 11:13:40.647075

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "498ade3999dd"
down_revision = "4d8d67396f79"
branch_labels = None
depends_on = None


def upgrade():
    # This mistake needs to be corrected
    op.alter_column(
        "commit",
        "branch",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=510),
    )
    # First allow this to be nullable, then fill it in and make it non-nullable
    op.add_column(
        "benchmark_result", sa.Column("is_step_change", sa.Boolean(), nullable=True)
    )
    op.execute("UPDATE benchmark_result SET is_step_change = false")
    op.alter_column("benchmark_result", "is_step_change", nullable=False)


def downgrade():
    op.alter_column(
        "commit",
        "branch",
        existing_type=sa.String(length=510),
        type_=sa.VARCHAR(length=100),
    )
    op.drop_column("benchmark_result", "is_step_change")
