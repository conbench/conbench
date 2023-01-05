"""add is_step_change column

Revision ID: 4efa955b2696
Revises: d3515ecea53d
Create Date: 2022-12-06 12:50:12.671498

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4efa955b2696"
down_revision = "d3515ecea53d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "benchmark_result", sa.Column("is_step_change", sa.Boolean(), nullable=False)
    )


def downgrade():
    op.drop_column("benchmark_result", "is_step_change")
