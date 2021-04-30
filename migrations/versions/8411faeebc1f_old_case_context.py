"""old case context

Revision ID: 8411faeebc1f
Revises: 4a5177dc4e44
Create Date: 2021-04-30 08:46:48.985283

"""
from alembic import op
from sqlalchemy import MetaData


# revision identifiers, used by Alembic.
revision = "8411faeebc1f"
down_revision = "4a5177dc4e44"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    case_table = meta.tables["case"]
    context_table = meta.tables["context"]
    where = case_table.c.tags.has_key("gc_collect")  # noqa
    connection.execute(case_table.delete().where(where))
    where = case_table.c.tags.has_key("gc_disable")  # noqa
    connection.execute(case_table.delete().where(where))
    where = context_table.c.tags.has_key("arrow_git_revision")  # noqa
    connection.execute(context_table.delete().where(where))


def downgrade():
    pass
