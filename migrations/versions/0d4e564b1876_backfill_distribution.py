import uuid

from alembic import op
from sqlalchemy import func, MetaData
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import select


revision = "0d4e564b1876"
down_revision = "0d44e2332557"
branch_labels = None
depends_on = None


def get_commit_index(commit_table, repository):
    ordered = (
        select(commit_table.c.id, commit_table.c.sha, commit_table.c.timestamp)
        .filter(commit_table.c.repository == repository)
        .order_by(commit_table.c.timestamp.desc())
    ).cte("ordered_commits")
    return select(ordered, func.row_number().over().label("row_number"))


def get_commits_up(commit_table, repository, sha, limit):
    index = get_commit_index(commit_table, repository).subquery().alias("commit_index")
    n = select(index.c.row_number).filter(index.c.sha == sha).scalar_subquery()
    return index.select().filter(index.c.row_number >= n).limit(limit)


def get_distribution(
    summary_table,
    run_table,
    machine_table,
    commit_table,
    repository,
    sha,
    machine_hash,
    limit,
):
    commits_up = (
        get_commits_up(commit_table, repository, sha, limit)
        .subquery()
        .alias("commits_up")
    )
    return (
        select(
            func.text(repository).label("repository"),
            func.text(sha).label("sha"),
            summary_table.c.case_id,
            summary_table.c.context_id,
            func.concat(
                machine_table.c.name,
                "-",
                machine_table.c.cpu_core_count,
                "-",
                machine_table.c.cpu_thread_count,
                "-",
                machine_table.c.memory_bytes,
            ).label("hash"),
            func.max(summary_table.c.unit).label("unit"),
            func.avg(summary_table.c.mean).label("mean_mean"),
            func.stddev(summary_table.c.mean).label("mean_sd"),
            func.avg(summary_table.c.min).label("min_mean"),
            func.stddev(summary_table.c.min).label("min_sd"),
            func.avg(summary_table.c.max).label("max_mean"),
            func.stddev(summary_table.c.max).label("max_sd"),
            func.avg(summary_table.c.median).label("median_mean"),
            func.stddev(summary_table.c.median).label("median_sd"),
            func.min(commits_up.c.timestamp).label("first_timestamp"),
            func.max(commits_up.c.timestamp).label("last_timestamp"),
            func.count(summary_table.c.mean).label("observations"),
        )
        .group_by(
            summary_table.c.case_id,
            summary_table.c.context_id,
            machine_table.c.name,
            machine_table.c.cpu_core_count,
            machine_table.c.cpu_thread_count,
            machine_table.c.memory_bytes,
        )
        .join(run_table, run_table.c.id == summary_table.c.run_id)
        .join(machine_table, machine_table.c.id == summary_table.c.machine_id)
        .join(commits_up, commits_up.c.id == run_table.c.commit_id)
        .filter(
            run_table.c.name.like("commit: %"),
            func.concat(
                machine_table.c.name,
                "-",
                machine_table.c.cpu_core_count,
                "-",
                machine_table.c.cpu_thread_count,
                "-",
                machine_table.c.memory_bytes,
            )
            == machine_hash,
        )
    )


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)

    commit_table = meta.tables["commit"]
    distribution_table = meta.tables["distribution"]
    machine_table = meta.tables["machine"]
    run_table = meta.tables["run"]
    summary_table = meta.tables["summary"]

    commits = connection.execute(commit_table.select())
    distributions = connection.execute(distribution_table.select())
    machines = connection.execute(machine_table.select())
    commits_by_id = {c["id"]: c for c in commits}
    machines_by_id = {m["id"]: m for m in machines}

    runs = connection.execute(
        run_table.select().filter(run_table.c.name.like("commit: %"))
    )
    for run in runs:
        commit = commits_by_id.get(run["commit_id"])
        if not commit:
            continue

        m = machines_by_id[run.machine_id]
        machine_hash = (
            f"{m.name}-{m.cpu_core_count}-{m.cpu_thread_count}-{m.memory_bytes}"
        )

        distributions = list(
            connection.execute(
                get_distribution(
                    summary_table,
                    run_table,
                    machine_table,
                    commit_table,
                    commit["repository"],
                    commit["sha"],
                    machine_hash,
                    1000,
                )
            )
        )

        for distribution in distributions:
            values = dict(distribution)
            machine_hash = values.pop("hash")
            values["id"] = uuid.uuid4().hex
            values["machine_hash"] = machine_hash

            connection.execute(
                insert(distribution_table)
                .values(values)
                .on_conflict_do_update(
                    index_elements=["sha", "case_id", "context_id", "machine_hash"],
                    set_=values,
                )
            )
            connection.commit()


def downgrade():
    pass
