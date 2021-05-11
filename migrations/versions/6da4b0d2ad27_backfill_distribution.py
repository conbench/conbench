"""backfill distribution

Revision ID: 6da4b0d2ad27
Revises: b7ffcaaeb240
Create Date: 2021-05-11 10:31:22.260237

"""
import uuid

from alembic import op
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import insert

from conbench.entities.distribution import get_distribution

# revision identifiers, used by Alembic.
revision = "6da4b0d2ad27"
down_revision = "b7ffcaaeb240"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)

    commit_table = meta.tables["commit"]
    distribution_table = meta.tables["distribution"]
    run_table = meta.tables["run"]
    summary_table = meta.tables["summary"]

    runs = connection.execute(run_table.select())
    commits = connection.execute(commit_table.select())
    runs_by_id = {r["id"]: r for r in runs}
    commits_by_id = {c["id"]: c for c in commits}

    summaries = connection.execute(summary_table.select())
    for summary in summaries:
        run = runs_by_id[summary["run_id"]]
        commit = commits_by_id[run["commit_id"]]

        distribution = get_distribution(
            commit["repository"],
            commit["sha"],
            summary["case_id"],
            summary["context_id"],
            summary["machine_id"],
            1000,
        ).first()

        if not distribution:
            continue

        values = dict(distribution)
        values["id"] = uuid.uuid4().hex

        connection.execute(
            insert(distribution_table)
            .values(values)
            .on_conflict_do_update(
                index_elements=["sha", "case_id", "context_id", "machine_id"],
                set_=values,
            )
        )
        connection.commit()


def downgrade():
    pass
