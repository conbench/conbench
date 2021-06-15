from alembic import op
from sqlalchemy import MetaData


revision = "854c3ba5abd6"
down_revision = "991493b6406a"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    case_table = meta.tables["case"]
    summary_table = meta.tables["summary"]

    cases = connection.execute(case_table.select())
    for case in cases:
        if "gc_collect" in case.tags or "gc_disable" in case.tags:
            new_tags = dict(case.tags)
            new_tags.pop("gc_collect")
            new_tags.pop("gc_disable")
            other = connection.execute(
                case_table.select().where(
                    case_table.c.name == case.name,
                    case_table.c.tags == new_tags,
                )
            ).fetchone()
            if other:
                connection.execute(
                    summary_table.update()
                    .where(summary_table.c.case_id == case.id)
                    .values(case_id=other.id)
                )
                connection.execute(
                    case_table.delete().where(case_table.c.id == case.id)
                )
            else:
                connection.execute(
                    case_table.update()
                    .where(case_table.c.id == case.id)
                    .values(tags=new_tags)
                )


def downgrade():
    pass
