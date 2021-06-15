from alembic import op
import sqlalchemy as sa
from sqlalchemy import MetaData


revision = "2d922b652c91"
down_revision = "2252bb39c5cf"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("distribution", sa.Column("limit", sa.Integer(), nullable=True))

    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    distribution_table = meta.tables["distribution"]

    connection.execute(
        distribution_table.update()
        .where(distribution_table.c.limit == None)  # noqa
        .values(limit=1000)
    )


def downgrade():
    op.drop_column("distribution", "limit")
