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
    hardware_hash = NotNull(s.String(250))
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
    "distribution_commit_hardware_index",
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


def get_distribution(benchmark_result, limit):
    from ..entities.benchmark_result import BenchmarkResult

    commits_up = (
        get_commits_up(benchmark_result.run.commit, limit)
        .subquery()
        .alias("commits_up")
    )

    return (
        Session.query(
            func.text(benchmark_result.case_id).label("case_id"),
            func.text(benchmark_result.context_id).label("context_id"),
            func.text(benchmark_result.run.commit_id).label("commit_id"),
            Hardware.hash.label("hash"),
            func.max(BenchmarkResult.unit).label("unit"),
            func.avg(BenchmarkResult.mean).label("mean_mean"),
            func.stddev(BenchmarkResult.mean).label("mean_sd"),
            func.avg(BenchmarkResult.min).label("min_mean"),
            func.stddev(BenchmarkResult.min).label("min_sd"),
            func.avg(BenchmarkResult.max).label("max_mean"),
            func.stddev(BenchmarkResult.max).label("max_sd"),
            func.avg(BenchmarkResult.median).label("median_mean"),
            func.stddev(BenchmarkResult.median).label("median_sd"),
            func.min(commits_up.c.timestamp).label("first_timestamp"),
            func.max(commits_up.c.timestamp).label("last_timestamp"),
            func.count(BenchmarkResult.mean).label("observations"),
        )
        .group_by(
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            Hardware.hash,
        )
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(commits_up, commits_up.c.id == Run.commit_id)
        .filter(
            Run.name.like("commit: %"),
            BenchmarkResult.case_id == benchmark_result.case_id,
            BenchmarkResult.context_id == benchmark_result.context_id,
            Hardware.hash == benchmark_result.run.hardware.hash,
        )
    )


def update_distribution(benchmark_result, limit):
    from ..db import engine

    if benchmark_result.run.commit.timestamp is None:
        return

    distribution = get_distribution(benchmark_result, limit).first()

    if not distribution:
        return

    values = dict(distribution)
    hardware_hash = values.pop("hash")
    values["hardware_hash"] = hardware_hash
    values["limit"] = limit

    with engine.connect() as conn:
        conn.execute(
            insert(Distribution.__table__)
            .values(values)
            .on_conflict_do_update(
                index_elements=["case_id", "context_id", "commit_id", "hardware_hash"],
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


def set_z_scores(benchmark_results):
    if not benchmark_results:
        return

    for benchmark_result in benchmark_results:
        benchmark_result.z_score = None

    first = benchmark_results[0]
    parent_commit = get_closest_parent(first.run)
    if not parent_commit:
        return

    where = [
        Distribution.commit_id == parent_commit.id,
        Distribution.hardware_hash == first.run.hardware.hash,
    ]
    if len(benchmark_results) == 1:
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

    for benchmark_result in benchmark_results:
        if benchmark_result.error:
            continue

        d = lookup.get(f"{benchmark_result.case_id}-{benchmark_result.context_id}")
        if d and d.mean_sd:
            benchmark_result.z_score = (benchmark_result.mean - d.mean_mean) / d.mean_sd
        if _less_is_better(benchmark_result.unit) and benchmark_result.z_score:
            benchmark_result.z_score = benchmark_result.z_score * -1
