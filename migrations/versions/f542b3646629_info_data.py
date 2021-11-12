"""info data

Revision ID: f542b3646629
Revises: 3ddd66ca34f2
Create Date: 2021-11-10 17:51:27.383747

"""
import logging
import uuid

from alembic import op
from sqlalchemy import MetaData, distinct, select

# revision identifiers, used by Alembic.
revision = "f542b3646629"
down_revision = "3ddd66ca34f2"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    info_table = meta.tables["info"]
    context_table = meta.tables["context"]
    summary_table = meta.tables["summary"]

    contexts = list(connection.execute(context_table.select()))
    num = len(contexts)
    for i, context in enumerate(contexts):
        logging.info(f"f542b3646629: Migrating context {i + 1} of {num}")
        info_tags, context_tags = {}, {}
        if "arrow_compiler_flags" in context.tags:
            info_tags = dict(context.tags)
            context_tags = {
                "benchmark_language": info_tags.pop("benchmark_language"),
                "arrow_compiler_flags": info_tags.pop("arrow_compiler_flags"),
            }
        else:
            context_tags = dict(context.tags)
            keys = [
                "description",
                "benchmark_language_version",
                "data_path",
            ]
            for key in keys:
                if key in context_tags:
                    value = context_tags.pop(key)
                    if value:
                        info_tags[key] = value
            keys = list(context_tags.keys())
            for key in keys:
                if key.endswith("_version"):
                    value = context_tags.pop(key)
                    if value:
                        info_tags[key] = value

        if not info_tags:
            continue

        other_info = connection.execute(
            info_table.select().where(
                info_table.c.tags == info_tags,
            )
        ).fetchone()

        if other_info:
            connection.execute(
                summary_table.update()
                .where(summary_table.c.context_id == context.id)
                .values(info_id=other_info.id)
            )
        else:
            new_info_id = uuid.uuid4().hex
            connection.execute(
                info_table.insert().values(
                    id=new_info_id,
                    tags=info_tags,
                )
            )
            connection.execute(
                summary_table.update()
                .where(summary_table.c.context_id == context.id)
                .values(info_id=new_info_id)
            )

        other_context = connection.execute(
            context_table.select().where(
                context_table.c.tags == context_tags,
            )
        ).fetchone()

        if other_context:
            connection.execute(
                summary_table.update()
                .where(summary_table.c.context_id == context.id)
                .values(context_id=other_context.id)
            )
        else:
            new_context_id = uuid.uuid4().hex
            connection.execute(
                context_table.insert().values(
                    id=new_context_id,
                    tags=context_tags,
                )
            )
            connection.execute(
                summary_table.update()
                .where(summary_table.c.context_id == context.id)
                .values(context_id=new_context_id)
            )

    context_ids = []
    logging.info("f542b3646629: Getting distinct contexts")
    result = connection.execute(select(distinct(summary_table.c.context_id)))
    for row in result:
        context_id = row[0]
        context_ids.append(context_id)

    info_ids = []
    logging.info("f542b3646629: Getting distinct info")
    result = connection.execute(select(distinct(summary_table.c.info_id)))
    for row in result:
        info_id = row[0]
        info_ids.append(info_id)

    logging.info("f542b3646629: Deleting unused contexts")
    for context in connection.execute(context_table.select()):
        if context.id not in context_ids:
            connection.execute(
                context_table.delete().where(context_table.c.id == context.id)
            )

    logging.info("f542b3646629: Deleting unused info")
    for info in connection.execute(info_table.select()):
        if info.id not in info_ids:
            connection.execute(info_table.delete().where(info_table.c.id == info.id))


def downgrade():
    pass
