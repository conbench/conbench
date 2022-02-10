"""update_machine_table

Revision ID: aa5092d7e206
Revises: 1c1ede4c924f
Create Date: 2022-02-10 14:30:39.595800

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "aa5092d7e206"
down_revision = "1c1ede4c924f"
branch_labels = None
depends_on = None


def set_machine_type():
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=connection)
    machine_table = meta.tables["machine"]
    connection.execute(machine_table.update().values(type="machine"))


def upgrade():
    op.add_column("machine", sa.Column("type", sa.String(length=50), nullable=True))
    op.add_column(
        "machine",
        sa.Column("info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("machine", sa.Column("hash", sa.String(length=1000), nullable=True))
    op.alter_column(
        "machine", "architecture_name", existing_type=sa.TEXT(), nullable=True
    )
    op.alter_column("machine", "kernel_name", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("machine", "os_name", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("machine", "os_version", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("machine", "cpu_model_name", existing_type=sa.TEXT(), nullable=True)
    op.alter_column(
        "machine", "cpu_l1d_cache_bytes", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_l1i_cache_bytes", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_l2_cache_bytes", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_l3_cache_bytes", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_core_count", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_thread_count", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "machine", "cpu_frequency_max_hz", existing_type=sa.BIGINT(), nullable=True
    )
    op.alter_column("machine", "memory_bytes", existing_type=sa.BIGINT(), nullable=True)
    op.alter_column("machine", "gpu_count", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column(
        "machine",
        "gpu_product_names",
        existing_type=postgresql.ARRAY(sa.TEXT()),
        nullable=True,
    )

    set_machine_type()

    op.alter_column(
        "machine", "type", existing_type=sa.VARCHAR(length=50), nullable=False
    )


def downgrade():
    op.alter_column(
        "machine",
        "gpu_product_names",
        existing_type=postgresql.ARRAY(sa.TEXT()),
        nullable=False,
    )
    op.alter_column("machine", "gpu_count", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column(
        "machine", "memory_bytes", existing_type=sa.BIGINT(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_frequency_max_hz", existing_type=sa.BIGINT(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_thread_count", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_core_count", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_l3_cache_bytes", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_l2_cache_bytes", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_l1i_cache_bytes", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_l1d_cache_bytes", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "machine", "cpu_model_name", existing_type=sa.TEXT(), nullable=False
    )
    op.alter_column("machine", "os_version", existing_type=sa.TEXT(), nullable=False)
    op.alter_column("machine", "os_name", existing_type=sa.TEXT(), nullable=False)
    op.alter_column("machine", "kernel_name", existing_type=sa.TEXT(), nullable=False)
    op.alter_column(
        "machine", "architecture_name", existing_type=sa.TEXT(), nullable=False
    )
    op.drop_column("machine", "hash")
    op.drop_column("machine", "info")
    op.drop_column("machine", "type")
