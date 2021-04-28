"""migrate contexts

Revision ID: 4a5177dc4e44
Revises: b5657b751fb5
Create Date: 2021-04-28 09:29:13.186747

"""
from alembic import op
from sqlalchemy import MetaData


# revision identifiers, used by Alembic.
revision = "4a5177dc4e44"
down_revision = "b5657b751fb5"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    context_table = meta.tables["context"]
    summary_table = meta.tables["summary"]

    contexts = connection.execute(context_table.select())
    for context in contexts:
        if "arrow_git_revision" in context.tags:
            new_tags = dict(context.tags)
            new_tags.pop("arrow_git_revision")
            other = connection.execute(
                context_table.select().where(
                    context_table.c.tags == new_tags,
                )
            ).fetchone()
            if other:
                connection.execute(
                    summary_table.update()
                    .where(summary_table.c.context_id == context.id)
                    .values(context_id=other.id)
                )
                context_table.delete().where(context_table.c.id == context.id)
            else:
                connection.execute(
                    context_table.update()
                    .where(context_table.c.id == context.id)
                    .values(tags=new_tags)
                )


def downgrade():
    pass
