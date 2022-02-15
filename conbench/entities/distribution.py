import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from ..db import Session
from ..entities._comparator import _less_is_better
from ..entities._entity import Base, EntityMixin, NotNull, Nullable, generate_uuid
from ..entities.commit import Commit
from ..entities.hardware import Hardware
from ..entities.run import Run


class Distribution(Base, EntityMixin):
    __tablename__ = "distribution"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    case_id = NotNull(s.String(50), s.ForeignKey("case.id", ondelete="CASCADE"))
    context_id = NotNull(s.String(50), s.ForeignKey("context.id", ondelete="CASCADE"))
    commit_id = NotNull(s.String(50), s.ForeignKey("commit.id", ondelete="CASCADE"))
    # machine table/columns are only renamed to hardware at code level but not at database level
    hardware_hash = NotNull("machine_hash", s.String(250))
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
    Distribution.case_id,
    Distribution.context_id,
    Distribution.commit_id,
    Distribution.hardware_hash,
    unique=True,
)

s.Index(
    "distribution_commit_machine_index",
    Distribution.commit_id,
    Distribution.hardware_hash,
)


def get_commits_up(commit, limit):
    # NOTE this query will fail if commit.timestamp is None
    return (
        Session.query(Commit.id, Commit.timestamp)
        .filter(Commit.repository == commit.repository)
        .filter(Commit.timestamp.isnot(None))
        .filter(Commit.timestamp <= commit.timestamp)
        .order_by(Commit.timestamp.desc())
        .limit(limit)
    )


def get_distribution(summary, limit):
    from ..entities.summary import Summary

    commits_up = (
        get_commits_up(summary.run.commit, limit).subquery().alias("commits_up")
    )

    return (
        Session.query(
            func.text(summary.case_id).label("case_id"),
            func.text(summary.context_id).label("context_id"),
            func.text(summary.run.commit_id).label("commit_id"),
            Hardware.hash.label("hash"),
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
            Hardware.hash,
        )
        .join(Run, Run.id == Summary.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(commits_up, commits_up.c.id == Run.commit_id)
        .filter(
            Run.name.like("commit: %"),
            Summary.case_id == summary.case_id,
            Summary.context_id == summary.context_id,
            Hardware.hash == summary.run.hardware.hash,
        )
    )


def update_distribution(summary, limit):
    from ..db import engine

    if summary.run.commit.timestamp is None:
        return

    distribution = get_distribution(summary, limit).first()

    if not distribution:
        return

    values = dict(distribution)
    hardware_hash = values.pop("hash")
    # machine table/columns are only renamed to hardware at code level but not at database level
    values["machine_hash"] = hardware_hash
    values["limit"] = limit

    with engine.connect() as conn:
        conn.execute(
            insert(Distribution.__table__)
            .values(values)
            .on_conflict_do_update(
                # machine table/columns are only renamed to hardware at code level but not at database level
                index_elements=["case_id", "context_id", "commit_id", "machine_hash"],
                set_=values,
            )
        )
        conn.commit()


def get_closest_parent(run):
    commit = run.commit
    if commit.timestamp is None:
        return None

    hardware_entities = Hardware.all(hash=run.hardware.hash)
    hardware_ids = set([m.id for m in hardware_entities])

    # TODO: what about matching contexts
    result = (
        Session.query(
            Run.id,
            Commit.id,
        )
        .join(Commit, Commit.id == Run.commit_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .filter(
            Run.name.like("commit: %"),
            Hardware.id.in_(hardware_ids),
            Commit.timestamp.isnot(None),
            Commit.timestamp < commit.timestamp,
            Commit.repository == commit.repository,
        )
        .order_by(Commit.timestamp.desc())
        .first()
    )

    parent = None
    if result:
        commit_id = result[1]
        parent = Commit.get(commit_id)

    return parent


def set_z_scores(summaries):
    if not summaries:
        return

    for summary in summaries:
        summary.z_score = None

    first = summaries[0]
    parent_commit = get_closest_parent(first.run)
    if not parent_commit:
        return

    where = [
        Distribution.commit_id == parent_commit.id,
        Distribution.hardware_hash == first.run.hardware.hash,
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
        d = lookup.get(f"{summary.case_id}-{summary.context_id}")
        if d and d.mean_sd:
            summary.z_score = (summary.mean - d.mean_mean) / d.mean_sd
        if _less_is_better(summary.unit) and summary.z_score:
            summary.z_score = summary.z_score * -1
