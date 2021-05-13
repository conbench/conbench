"""merge machines

Revision ID: d91083587a7e
Revises: 6da4b0d2ad27
Create Date: 2021-05-13 17:25:08.493944

"""
from alembic import op
from sqlalchemy import MetaData


# revision identifiers, used by Alembic.
revision = "d91083587a7e"
down_revision = "6da4b0d2ad27"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    machine_table = meta.tables["machine"]
    run_table = meta.tables["run"]
    summary_table = meta.tables["summary"]
    # TODO


def downgrade():
    pass
