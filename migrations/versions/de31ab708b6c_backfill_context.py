"""backfill context

Revision ID: de31ab708b6c
Revises: 52b6915e289a
Create Date: 2021-04-26 13:10:55.281793

"""
from alembic import op
from sqlalchemy import MetaData


# revision identifiers, used by Alembic.
revision = "de31ab708b6c"
down_revision = "52b6915e289a"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    run_table = meta.tables["run"]
    summary_table = meta.tables["summary"]

    runs = connection.execute(
        run_table.select().where(run_table.c.context_id == None)  # noqa
    )
    for run in runs:
        benchmarks = list(
            connection.execute(
                summary_table.select()
                .where(
                    summary_table.c.run_id == run.id,
                )
                .limit(1)
            )
        )
        if benchmarks:
            benchmark = benchmarks[0]
            connection.execute(
                run_table.update()
                .where(run_table.c.id == run.id)
                .values(context_id=benchmark.context_id)
            )


def downgrade():
    pass
