from alembic import op
import sqlalchemy as sa
from sqlalchemy import MetaData


revision = "afc565181834"
down_revision = "2d922b652c91"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    distribution_table = meta.tables["distribution"]

    connection.execute(
        distribution_table.update()
        .where(distribution_table.c.limit == None)  # noqa
        .values(limit=1000)
    )

    op.alter_column("distribution", "limit", existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    op.alter_column("distribution", "limit", existing_type=sa.INTEGER(), nullable=True)
