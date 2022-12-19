import logging
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Query

from ..db import Session
from ..entities._comparator import _less_is_better
from ..entities._entity import Base, EntityMixin, NotNull, Nullable, generate_uuid
from ..entities.commit import CantFindAncestorCommitsError, Commit
from ..entities.hardware import Hardware
from ..entities.run import Run

if TYPE_CHECKING:
    from ..entities.benchmark_result import BenchmarkResult

log = logging.getLogger(__name__)


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


def _distribution_query(
    benchmark_result: "BenchmarkResult", commit_limit: int
) -> Query:
    """Return a query that returns 0 or 1 row, giving statistics about the set of
    error-free BenchmarkResults that share the given benchmark_result's case, context,
    and hardware, and that are in the given benchmark_result's direct commit ancestry,
    including the given benchmark_result's commit up to some given limit of ancestor
    commits.

    Might raise CantFindAncestorCommitsError.
    """
    from ..entities.benchmark_result import BenchmarkResult

    commit: Commit = benchmark_result.run.commit
    ancestor_commits = (
        commit.commit_ancestry_query.order_by(s.desc("commit_order"))
        .limit(commit_limit)
        .subquery()
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
            func.min(ancestor_commits.c.ancestor_timestamp).label("first_timestamp"),
            func.max(ancestor_commits.c.ancestor_timestamp).label("last_timestamp"),
            func.count(BenchmarkResult.mean).label("observations"),
        )
        .group_by(
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            Hardware.hash,
        )
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(ancestor_commits, ancestor_commits.c.ancestor_id == Run.commit_id)
        .filter(
            BenchmarkResult.error.is_(None),
            BenchmarkResult.case_id == benchmark_result.case_id,
            BenchmarkResult.context_id == benchmark_result.context_id,
            Hardware.hash == benchmark_result.run.hardware.hash,
        )
    )


def update_distribution(
    benchmark_result: "BenchmarkResult", commit_limit: int
) -> Optional[dict]:
    """Try to upsert a Distribution table row, with the given benchmark_result as the
    most recent BenchmarkResult in the distribution.

    Returns a dict of values if those values were upserted, else returns None. Should
    not raise anything.
    """
    try:
        distribution_query = _distribution_query(benchmark_result, commit_limit)
    except CantFindAncestorCommitsError as e:
        log.debug(
            f"Not updating distribution: couldn't find ancestor commits, because {e}"
        )
        return None

    distribution = distribution_query.first()
    if not distribution:
        log.debug("Not updating distribution: the distribution query returned 0 rows")
        return None

    values = dict(distribution)
    hardware_hash = values.pop("hash")
    values["hardware_hash"] = hardware_hash
    values["limit"] = commit_limit

    Session.execute(
        insert(Distribution.__table__)
        .values(values)
        .on_conflict_do_update(
            index_elements=["case_id", "context_id", "commit_id", "hardware_hash"],
            set_=values,
        )
    )
    Session.commit()
    return values


def get_closest_ancestor(
    benchmark_result: "BenchmarkResult", branch: Optional[str] = None
) -> Optional[Commit]:
    """Given a BenchmarkResult, return the most recent ancestor commit on the given
    branch that also has a BenchmarkResult in the database with the same
    hardware/case/context. If branch is not given (default), search all branches.

    Return None if one isn't found. Should not raise anything.
    """
    from ..entities.benchmark_result import BenchmarkResult

    commit: Commit = benchmark_result.run.commit
    try:
        ancestor_commits = commit.commit_ancestry_query.subquery()
    except CantFindAncestorCommitsError as e:
        log.debug(f"Couldn't find closest ancestor because {e}")
        return None

    query = (
        Session.query(BenchmarkResult)
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(ancestor_commits, ancestor_commits.c.ancestor_id == Run.commit_id)
        .filter(
            BenchmarkResult.case_id == benchmark_result.case_id,
            BenchmarkResult.context_id == benchmark_result.context_id,
            Hardware.hash == benchmark_result.run.hardware.hash,
            ancestor_commits.c.ancestor_id != commit.id,
        )
    )
    if branch:
        # TODO: hack for now, will replace this function later
        query = query.filter(ancestor_commits.c.commit_order.like("1_%"))

    closest_benchmark_result = query.order_by(
        ancestor_commits.c.commit_order.desc()
    ).first()

    if not closest_benchmark_result:
        log.debug(
            "Couldn't find closest ancestor: there were no matching BenchmarkResults"
        )
        return None

    return closest_benchmark_result.run.commit


def set_z_scores(benchmark_results: List["BenchmarkResult"]):
    """Populate the "z_score" attribute of each given BenchmarkResult, comparing it to
    the distribution of BenchmarkResults that share the same hardware/case/context,
    ending with the most recent BenchmarkResult in the given BenchmarkResult's commit
    ancestry on the default branch.

    We choose a commit from the default branch as the end commit, because we probably
    don't want "bad" commits early on in a PR to set artificially low z-scores later in
    the PR.

    For the start commit of the distribution, uses whatever commit_limit was used when
    writing to the Distribution table.

    Should not raise anything. If we can't find a z-score for some reason, the z_score
    attribute will be None on that BenchmarkResult.
    """
    if not benchmark_results:
        return

    # Find the default branch first. If we can't find it, we'll just find the closest
    # ancestor commit to each BenchmarkResult regardless of branch, which isn't ideal
    # (see docstring) but it's good enough.
    a_default_commit = benchmark_results[0].run.commit.get_fork_point_commit()
    default_branch = a_default_commit.branch if a_default_commit else None

    # Cache Distribution query results by commit/hardware/case/context, in case multiple
    # input benchmark_results (e.g. from the same Run) share those attributes
    cached_distributions = {}

    for benchmark_result in benchmark_results:
        benchmark_result.z_score = None
        if benchmark_result.error:
            continue

        closest_ancestor = get_closest_ancestor(benchmark_result, branch=default_branch)
        if not closest_ancestor:
            log.debug("Setting benchmark_result.z_score = None")
            continue

        commit = closest_ancestor.id
        hardware = benchmark_result.run.hardware.hash
        case = benchmark_result.case_id
        context = benchmark_result.context_id

        if (commit, hardware, case, context) in cached_distributions:
            distribution = cached_distributions[(commit, hardware, case, context)]
        else:
            distribution = (
                Session.query(Distribution)
                .filter_by(
                    commit_id=commit,
                    hardware_hash=hardware,
                    case_id=case,
                    context_id=context,
                )
                .first()
            )
            cached_distributions[(commit, hardware, case, context)] = distribution

        if (
            benchmark_result.mean is not None
            and distribution
            and distribution.mean_mean is not None
            and distribution.mean_sd  # is positive
        ):
            benchmark_result.z_score = (
                benchmark_result.mean - distribution.mean_mean
            ) / distribution.mean_sd

        if _less_is_better(benchmark_result.unit) and benchmark_result.z_score:
            benchmark_result.z_score = benchmark_result.z_score * -1
