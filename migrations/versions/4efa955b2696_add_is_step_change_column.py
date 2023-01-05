"""add is_step_change column

Revision ID: 4efa955b2696
Revises: 4d8d67396f79
Create Date: 2022-12-06 12:50:12.671498

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4efa955b2696"
down_revision = "4d8d67396f79"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "benchmark_result", sa.Column("is_step_change", sa.Boolean(), nullable=False)
    )


def downgrade():
    op.drop_column("benchmark_result", "is_step_change")
