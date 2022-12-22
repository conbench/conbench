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
    # Cache Distribution query results by commit/hardware, in case multiple input
    # benchmark_results (e.g. from the same Run) share those attributes
    cached_distributions = {}
    # Also cache respective baseline runs by each Run's ID. Note that two
    # benchmark_results from the same Run might not have the exact same baseline run,
    # because one baseline run might be missing the case/context of the other
    # benchmark_result. In those cases, we might fail to populate the z-score of the
    # second benchmark result. But that's too rare and small-impact to justify not
    # caching for performance reasons.
    cached_baseline_runs = {}

    for benchmark_result in benchmark_results:
        benchmark_result.z_score = None
        if benchmark_result.error:
            log.debug("benchmark_result has error; setting z_score = None")
            continue

        if benchmark_result.run_id in cached_baseline_runs:
            baseline_run = cached_baseline_runs[benchmark_result.run_id]
        else:
            baseline_run = benchmark_result.run.get_baseline_run(
                on_default_branch=True,
                case_id=benchmark_result.case_id,
                context_id=benchmark_result.context_id,
            )
            cached_baseline_runs[benchmark_result.run_id] = baseline_run

        if not baseline_run:
            log.debug("No baseline run; setting benchmark_result.z_score = None")
            continue

        commit = baseline_run.commit_id
        hardware = baseline_run.hardware.hash

        if (commit, hardware) in cached_distributions:
            distributions = cached_distributions[(commit, hardware)]
        else:
            distributions = (
                Session.query(Distribution)
                .filter_by(commit_id=commit, hardware_hash=hardware)
                .all()
            )
            cached_distributions[(commit, hardware)] = distributions

        # based on the unique index, this list should either have length 0 or 1
        matching_distributions = [
            distribution
            for distribution in distributions
            if distribution.case_id == benchmark_result.case_id
            and distribution.context_id == benchmark_result.context_id
        ]

        if (
            benchmark_result.mean is not None
            and matching_distributions
            and matching_distributions[0].mean_mean is not None
            and matching_distributions[0].mean_sd  # is positive
        ):
            benchmark_result.z_score = (
                benchmark_result.mean - matching_distributions[0].mean_mean
            ) / matching_distributions[0].mean_sd

        if _less_is_better(benchmark_result.unit) and benchmark_result.z_score:
            benchmark_result.z_score = benchmark_result.z_score * -1
