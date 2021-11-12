import logging
import uuid

from alembic import op
from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import select

revision = "9fed559406c5"
down_revision = "f542b3646629"
branch_labels = None
depends_on = None


def get_commits_up(commit_table, repository, sha, limit):
    commit = (
        select(commit_table.c.timestamp)
        .filter(commit_table.c.repository == repository)
        .filter(commit_table.c.sha == sha)
        .scalar_subquery()
    )
    return (
        select(commit_table.c.id, commit_table.c.timestamp)
        .filter(commit_table.c.repository == repository)
        .filter(commit_table.c.timestamp.isnot(None))
        .filter(commit_table.c.timestamp <= commit)
        .order_by(commit_table.c.timestamp.desc())
        .limit(limit)
    )


def get_distribution(
    summary_table,
    run_table,
    machine_table,
    commit_table,
    repository,
    sha,
    case_id,
    context_id,
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
            summary_table.c.case_id,
            summary_table.c.context_id,
            run_table.c.commit_id,
            func.concat(
                machine_table.c.name,
                "-",
                machine_table.c.gpu_count,
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
            run_table.c.commit_id,
            machine_table.c.name,
            machine_table.c.gpu_count,
            machine_table.c.cpu_core_count,
            machine_table.c.cpu_thread_count,
            machine_table.c.memory_bytes,
        )
        .join(run_table, run_table.c.id == summary_table.c.run_id)
        .join(machine_table, machine_table.c.id == run_table.c.machine_id)
        .join(commits_up, commits_up.c.id == run_table.c.commit_id)
        .filter(
            run_table.c.name.like("commit: %"),
            summary_table.c.case_id == case_id,
            summary_table.c.context_id == context_id,
            func.concat(
                machine_table.c.name,
                "-",
                machine_table.c.gpu_count,
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

    runs = connection.execute(run_table.select())
    commits = connection.execute(commit_table.select())
    distributions = connection.execute(distribution_table.select())
    machines = connection.execute(machine_table.select())
    runs_by_id = {r["id"]: r for r in runs}
    commits_by_id = {c["id"]: c for c in commits}
    machines_by_id = {m["id"]: m for m in machines}

    logging.info("9fed559406c5: Get benchmarks")
    summaries = connection.execute(
        summary_table.select()
        .join(run_table, run_table.c.id == summary_table.c.run_id)
        .filter(run_table.c.name.like("commit: %"))
    )

    i = 1

    logging.info("9fed559406c5: Truncate distribution table")
    connection.execute(distribution_table.delete())
    assert list(connection.execute(distribution_table.select())) == []

    for summary in summaries:
        run = runs_by_id.get(summary["run_id"])
        if not run:
            continue

        commit = commits_by_id.get(run["commit_id"])
        if not commit:
            continue

        m = machines_by_id[run["machine_id"]]
        machine_hash = f"{m.name}-{m.gpu_count}-{m.cpu_core_count}-{m.cpu_thread_count}-{m.memory_bytes}"

        distributions = list(
            connection.execute(
                get_distribution(
                    summary_table,
                    run_table,
                    machine_table,
                    commit_table,
                    commit["repository"],
                    commit["sha"],
                    summary["case_id"],
                    summary["context_id"],
                    machine_hash,
                    100,
                )
            )
        )

        if not distributions:
            continue

        distribution = distributions[0]
        values = dict(distribution)
        machine_hash = values.pop("hash")
        values["id"] = uuid.uuid4().hex
        values["machine_hash"] = machine_hash
        values["limit"] = 100

        connection.execute(
            insert(distribution_table)
            .values(values)
            .on_conflict_do_update(
                index_elements=["case_id", "context_id", "commit_id", "machine_hash"],
                set_=values,
            )
        )
        logging.info(f"9fed559406c5: Processed {i} summary")
        i += 1

    logging.info("9fed559406c5: Done with migration")


def downgrade():
    pass
