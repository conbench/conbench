import sqlalchemy as s
from sqlalchemy import func
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects.postgresql import insert

from ..db import Session
from ..entities._entity import (
    Base,
    EntityMixin,
    generate_uuid,
    NotNull,
    Nullable,
)
from ..entities._comparator import _less_is_better
from ..entities.commit import Commit
from ..entities.machine import Machine
from ..entities.run import Run


class Distribution(Base, EntityMixin):
    __tablename__ = "distribution"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    repository = NotNull(s.String(100))
    case_id = NotNull(s.String(50), s.ForeignKey("case.id", ondelete="CASCADE"))
    context_id = NotNull(s.String(50), s.ForeignKey("context.id", ondelete="CASCADE"))
    machine_hash = NotNull(s.String(250))
    unit = NotNull(s.Text)
    mean_mean = Nullable(s.Numeric, check("mean_mean>=0"))
    mean_sd = Nullable(s.Numeric, check("mean_sd>=0"))
    min_mean = Nullable(s.Numeric, check("min_mean>=0"))
    min_sd = Nullable(s.Numeric, check("min_sd>=0"))
    max_mean = Nullable(s.Numeric, check("max_mean>=0"))
    max_sd = Nullable(s.Numeric, check("max_sd>=0"))
    median_mean = Nullable(s.Numeric, check("median_mean>=0"))
    median_sd = Nullable(s.Numeric, check("median_sd>=0"))
    first_timestamp = NotNull(s.DateTime(timezone=False))
    last_timestamp = NotNull(s.DateTime(timezone=False))
    observations = NotNull(s.Integer, check("observations>=1"))
    limit = NotNull(s.Integer, check('"limit">=1'))


s.Index(
    "distribution_index",
    Distribution.sha,
    Distribution.case_id,
    Distribution.context_id,
    Distribution.machine_hash,
    unique=True,
)
s.Index("distribution_sha_index", Distribution.sha)
s.Index("distribution_repository_index", Distribution.repository)
s.Index("distribution_case_id_index", Distribution.case_id)
s.Index("distribution_context_id_index", Distribution.context_id)
s.Index("distribution_machine_hash_index", Distribution.machine_hash)


def get_commit_index(repository):
    ordered = (
        Session.query(Commit.id, Commit.sha, Commit.timestamp)
        .filter(Commit.repository == repository)
        .order_by(Commit.timestamp.desc())
    ).cte("ordered_commits")
    return Session.query(ordered, func.row_number().over().label("row_number"))


def get_sha_row_number(repository, sha):
    index = get_commit_index(repository).subquery().alias("commit_index")
    return Session.query(index.c.row_number).filter(index.c.sha == sha)


def get_commits_up(repository, sha, limit):
    index = get_commit_index(repository).subquery().alias("commit_index")
    n = Session.query(index.c.row_number).filter(index.c.sha == sha).scalar_subquery()
    return Session.query(index).filter(index.c.row_number >= n).limit(limit)


def get_distribution(repository, sha, case_id, context_id, machine_hash, limit):
    from ..entities.summary import Summary

    commits_up = get_commits_up(repository, sha, limit).subquery().alias("commits_up")
    return (
        Session.query(
            func.text(repository).label("repository"),
            func.text(sha).label("sha"),
            Summary.case_id,
            Summary.context_id,
            Machine.hash,
            func.max(Summary.unit).label("unit"),
            func.avg(Summary.mean).label("mean_mean"),
            func.stddev(Summary.mean).label("mean_sd"),
            func.avg(Summary.min).label("min_mean"),
            func.stddev(Summary.min).label("min_sd"),
            func.avg(Summary.max).label("max_mean"),
            func.stddev(Summary.max).label("max_sd"),
            func.avg(Summary.median).label("median_mean"),
            func.stddev(Summary.median).label("median_sd"),
            func.min(commits_up.c.timestamp).label("first_timestamp"),
            func.max(commits_up.c.timestamp).label("last_timestamp"),
            func.count(Summary.mean).label("observations"),
        )
        .group_by(
            Summary.case_id,
            Summary.context_id,
            Machine.name,
            Machine.cpu_core_count,
            Machine.cpu_thread_count,
            Machine.memory_bytes,
        )
        .join(Run, Run.id == Summary.run_id)
        .join(Machine, Machine.id == Run.machine_id)
        .join(commits_up, commits_up.c.id == Run.commit_id)
        .filter(
            Run.name.like("commit: %"),
            Summary.case_id == case_id,
            Summary.context_id == context_id,
            Machine.hash == machine_hash,
        )
    )


def update_distribution(repository, sha, summary, limit):
    from ..db import engine

    distribution = get_distribution(
        repository,
        sha,
        summary.case_id,
        summary.context_id,
        summary.run.machine.hash,
        limit,
    ).first()

    if not distribution:
        return

    values = dict(distribution)
    machine_hash = values.pop("hash")
    values["machine_hash"] = machine_hash
    values["limit"] = limit

    with engine.connect() as conn:
        conn.execute(
            insert(Distribution.__table__)
            .values(values)
            .on_conflict_do_update(
                index_elements=["sha", "case_id", "context_id", "machine_hash"],
                set_=values,
            )
        )
        conn.commit()


def set_z_scores(summaries):
    if not summaries:
        return

    first = summaries[0]
    repository = first.run.commit.repository
    sha = first.run.commit.parent
    machine_hash = first.run.machine.hash

    where = [
        Distribution.repository == repository,
        Distribution.sha == sha,
        Distribution.machine_hash == machine_hash,
    ]
    if len(summaries) == 1:
        where.extend(
            [
                Distribution.case_id == first.case_id,
                Distribution.context_id == first.context_id,
            ]
        )

    cols = [
        Distribution.case_id,
        Distribution.context_id,
        Distribution.mean_mean,
        Distribution.mean_sd,
    ]
    distributions = Session.query(*cols).filter(*where).all()
    lookup = {f"{d.case_id}-{d.context_id}": d for d in distributions}

    for summary in summaries:
        summary.z_score = 0
        d = lookup.get(f"{summary.case_id}-{summary.context_id}")
        if d and d.mean_sd:
            summary.z_score = (summary.mean - d.mean_mean) / d.mean_sd
        if _less_is_better(summary.unit) and summary.z_score != 0:
            summary.z_score = summary.z_score * -1
