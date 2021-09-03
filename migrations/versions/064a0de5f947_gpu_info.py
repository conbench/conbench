"""gpu info

Revision ID: 064a0de5f947
Revises: ab19aaf54876
Create Date: 2021-09-03 11:00:08.205984

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "064a0de5f947"
down_revision = "ab19aaf54876"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("machine", sa.Column("gpu_count", sa.Integer(), nullable=True))
    op.add_column(
        "machine",
        sa.Column("gpu_product_names", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.drop_index("machine_index", table_name="machine")
    op.create_index(
        "machine_index",
        "machine",
        [
            "name",
            "architecture_name",
            "kernel_name",
            "os_name",
            "os_version",
            "cpu_model_name",
            "cpu_l1d_cache_bytes",
            "cpu_l1i_cache_bytes",
            "cpu_l2_cache_bytes",
            "cpu_l3_cache_bytes",
            "cpu_core_count",
            "cpu_thread_count",
            "cpu_frequency_max_hz",
            "memory_bytes",
            "gpu_count",
            "gpu_product_names",
        ],
        unique=True,
    )


def downgrade():
    op.drop_index("machine_index", table_name="machine")
    op.create_index(
        "machine_index",
        "machine",
        [
            "name",
            "architecture_name",
            "kernel_name",
            "os_name",
            "os_version",
            "cpu_model_name",
            "cpu_l1d_cache_bytes",
            "cpu_l1i_cache_bytes",
            "cpu_l2_cache_bytes",
            "cpu_l3_cache_bytes",
            "cpu_core_count",
            "cpu_thread_count",
            "cpu_frequency_max_hz",
            "memory_bytes",
        ],
        unique=False,
    )
    op.drop_column("machine", "gpu_product_names")
    op.drop_column("machine", "gpu_count")
