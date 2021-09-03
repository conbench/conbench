"""gpu info not null

Revision ID: 8a72866f991c
Revises: 064a0de5f947
Create Date: 2021-09-03 12:25:25.521817

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8a72866f991c"
down_revision = "064a0de5f947"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    machine_table = meta.tables["machine"]

    connection.execute(
        machine_table.update()
        .where(machine_table.c.gpu_count == None)  # noqa
        .values(gpu_count=0)
    )
    connection.execute(
        machine_table.update()
        .where(machine_table.c.gpu_product_names == None)  # noqa
        .values(gpu_product_names=[])
    )

    op.alter_column("machine", "gpu_count", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column(
        "machine",
        "gpu_product_names",
        existing_type=postgresql.ARRAY(sa.TEXT()),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "machine",
        "gpu_product_names",
        existing_type=postgresql.ARRAY(sa.TEXT()),
        nullable=True,
    )
    op.alter_column("machine", "gpu_count", existing_type=sa.INTEGER(), nullable=True)
