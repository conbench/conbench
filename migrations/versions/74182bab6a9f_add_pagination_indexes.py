"""add pagination indexes

Revision ID: 74182bab6a9f
Revises: 9bee3b519bf1
Create Date: 2023-10-17 15:26:26.623525

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "74182bab6a9f"
down_revision = "9bee3b519bf1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "benchmark_result_id_idx",
        "benchmark_result",
        ["id"],
        unique=False,
        postgresql_where=sa.text("timestamp >= '2023-06-03'"),
    )
    op.create_index(
        "benchmark_result_run_reason_id_idx",
        "benchmark_result",
        ["run_reason", "id"],
        unique=False,
        postgresql_where=sa.text("timestamp >= '2023-06-03'"),
    )


def downgrade():
    op.drop_index(
        "benchmark_result_run_reason_id_idx",
        table_name="benchmark_result",
        postgresql_where=sa.text("timestamp >= '2023-06-03'"),
    )
    op.drop_index(
        "benchmark_result_id_idx",
        table_name="benchmark_result",
        postgresql_where=sa.text("timestamp >= '2023-06-03'"),
    )
