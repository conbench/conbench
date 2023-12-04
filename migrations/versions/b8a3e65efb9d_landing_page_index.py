"""landing_page_index

Revision ID: b8a3e65efb9d
Revises: 74182bab6a9f
Create Date: 2023-12-04 16:45:12.036321

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8a3e65efb9d"
down_revision = "74182bab6a9f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "benchmark_result_run_id_timestamp_idx",
        "benchmark_result",
        ["run_id", "timestamp"],
        unique=False,
        postgresql_where=sa.text("timestamp >= '2023-11-19'"),
    )


def downgrade():
    op.drop_index(
        "benchmark_result_run_id_timestamp_idx",
        table_name="benchmark_result",
        postgresql_where=sa.text("timestamp >= '2023-11-19'"),
    )
