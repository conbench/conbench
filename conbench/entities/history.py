import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import sqlalchemy as s

from ..config import Config
from ..db import Session
from ..entities._comparator import _less_is_better
from ..entities._entity import EntitySerializer
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import CantFindAncestorCommitsError, Commit
from ..entities.hardware import Hardware
from ..entities.run import Run

log = logging.getLogger(__name__)

# NOTE: Unlike other modules in this directory, the concept of "history" is not
# explicitly represented in the database as a table, but we still need to define common
# logic for statistical analysis of historic distributions. This module does that.
#
# It includes functions to power the history API, and to set z-scores on
# BenchmarkResults, because that's fundamentally related to their histories.


class _Serializer(EntitySerializer):
    def _dump(self, history):
        # Note(JP): expose `times` or `data` or flatten them or expose both?
        # Unclear. `times` is specified as "A list of benchmark durations. If
        # data is a duration measure, this should be a duplicate of that
        # object." `data` is specified with "A list of benchmark results (e.g.
        # durations, throughput). This will be used as the main + only metric
        # for regression and improvement. The values should be ordered in the
        # order the iterations were executed (the first element is the first
        # iteration, the second element is the second iteration, etc.). If an
        # iteration did not complete but others did and you want to send
        # partial data, mark each iteration that didn't complete as null."
        # Expose both for now.
        #
        # In practice, I have only seen `data` being used so far and even when
        # `data` was representing durations then this vector was not duplicated
        # as `times`.

        # For both, history.data and history.times expect either None or a list
        # Make it so that in the output object they are always a list,
        # potentially empty. `data` contains more than one value if this was
        # a multi-sample benchmark.
        data = []
        if history.data is not None:
            data = [float(d) if d is not None else None for d in history.data]

        times = []
        if history.times is not None:
            times = [float(t) if t is not None else None for t in history.times]

        return {
            "benchmark_id": history.id,
            "case_id": history.case_id,
            "context_id": history.context_id,
            "mean": float(history.mean),
            "data": data,
            "times": times,
            "unit": history.unit,
            "begins_distribution_change": history.begins_distribution_change,
            "hardware_hash": history.hash,
            "sha": history.sha,
            "repository": history.repository,
            # Note(JP): this is the commit message
            "message": history.message,
            # This is the Commit timestamp. Expose Result timestamp, too?
            "timestamp": history.timestamp.isoformat(),
            "run_name": history.name,
            "distribution_mean": float(history.rolling_mean),
            "distribution_stdev": float(history.rolling_stddev or 0),
        }


class HistorySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def get_history(case_id: str, context_id: str, hardware_hash: str, repo: str) -> list:
    """Given a case/context/hardware/repo, return all non-errored BenchmarkResults
    (past, present, and future) on the default branch that match those criteria, along
    with information about the stats of the distribution as of each BenchmarkResult.
    Order is not guaranteed. Used to power the history API, which also powers the
    timeseries plots.

    For further detail on the stats columns, see the docs of
    ``_add_rolling_stats_columns_to_history_query()``.
    """
    history = (
        Session.query(
            BenchmarkResult.id,
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            BenchmarkResult.mean,
            BenchmarkResult.unit,
            BenchmarkResult.data,
            BenchmarkResult.times,
            BenchmarkResult.change_annotations,
            Hardware.hash,
            Commit.sha,
            Commit.repository,
            Commit.message,
            Commit.timestamp,
            Run.name,
        )
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(Commit, Commit.id == Run.commit_id)
        .filter(
            BenchmarkResult.case_id == case_id,
            BenchmarkResult.context_id == context_id,
            BenchmarkResult.error.is_(None),
            Commit.sha == Commit.fork_point_sha,  # on default branch
            Commit.repository == repo,
            Hardware.hash == hardware_hash,
        )
        .subquery()
    )

    history = _add_rolling_stats_columns_to_history_query(
        history, include_current_commit_in_rolling_stats=False
    )

    return Session.query(history).all()


def set_z_scores(benchmark_results: List[BenchmarkResult]):
    """Set the "z_score" attribute on each given BenchmarkResult, comparing it to the
    distribution of BenchmarkResults that share the same case/context/hardware/repo,
    ending with the most recent BenchmarkResult in the given BenchmarkResult's commit
    ancestry on the default branch. (We choose a commit from the default branch as the
    end commit, because we probably don't want "bad" commits early on in a PR to set
    artificially low z-scores later in the PR.)

    This function does not affect the database whatsoever. It only populates an
    attribute on the given python objects. This is typically called right before
    returning a jsonify-ed response from the API, so the "z_score" attribute shouldn't
    already be set, but if it is already set, it will be silently overwritten.

    Should not raise anything. If we can't find a z-score for some reason, the z_score
    attribute will be None on that BenchmarkResult.
    """
    # For most invocations of this function, there are very few unique run_ids among the
    # benchmark_results. Sort them by run_id and run an optimized query for each group.
    sorted_by_run_id = defaultdict(list)
    for benchmark_result in benchmark_results:
        sorted_by_run_id[benchmark_result.run_id].append(benchmark_result)

    for run_id, result_group in sorted_by_run_id.items():
        if len(result_group) == 1:
            # performance optimization
            case_id = result_group[0].case_id
            context_id = result_group[0].context_id
        else:
            case_id = None
            context_id = None

        distribution_stats = _query_distribution_stats_by_run_id(
            run_id, case_id=case_id, context_id=context_id
        )

        for benchmark_result in result_group:
            dist_mean, dist_stddev = distribution_stats.get(
                (benchmark_result.case_id, benchmark_result.context_id), (None, None)
            )
            benchmark_result.z_score = _calculate_z_score(
                data_point=benchmark_result.mean,
                unit=benchmark_result.unit,
                dist_mean=dist_mean,
                dist_stddev=dist_stddev,
            )


def _query_distribution_stats_by_run_id(
    run_id: str, case_id: Optional[str], context_id: Optional[str]
) -> Dict[Tuple[str, str], Tuple[Optional[float], Optional[float]]]:
    """Given a run_id, return stats of the distribution of BenchmarkResults in the run's
    commit ancestry, by case/context. Returns a dict that looks like

    ``{(case_id, context_id): (dist_mean, dist_stddev)}``

    If case_id and context_id are given, only return that pair, not all pairs for the
    run. This saves some time.

    For further detail on the stats columns, see the docs of
    ``_add_rolling_stats_columns_to_history_query()``.
    """
    run = Run.get(run_id)

    try:
        commits = run.commit.commit_ancestry_query.subquery()
    except CantFindAncestorCommitsError as e:
        log.debug(f"Couldn't _query_distribution_stats_by_run_id() because {e}")
        return {}

    # Get the last DISTRIBUTION_COMMITS ancestor commits on the default branch
    commits = (
        Session.query(commits)
        .filter(
            commits.c.on_default_branch.is_(True),
            commits.c.ancestor_id != run.commit_id,
        )
        .order_by(commits.c.commit_order.desc())
        .limit(Config.DISTRIBUTION_COMMITS)
        .subquery()
    )

    # Find all historic commits in the distribution to analyze
    history = (
        Session.query(
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            BenchmarkResult.change_annotations,
            BenchmarkResult.mean,
            Hardware.hash,
            s.sql.expression.literal(run.commit.repository).label("repository"),
            commits.c.ancestor_timestamp.label("timestamp"),
        )
        .select_from(BenchmarkResult)
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(commits, commits.c.ancestor_id == Run.commit_id)
        .filter(BenchmarkResult.error.is_(None), Hardware.hash == run.hardware.hash)
    )

    # Filter to the correct case(s)/context(s)
    if case_id and context_id:
        # filter to the given case/context
        history = history.filter(
            BenchmarkResult.case_id == case_id,
            BenchmarkResult.context_id == context_id,
        )
    else:
        # filter to *any* case/context attached to this Run
        these_cases_and_contexts = (
            Session.query(BenchmarkResult.case_id, BenchmarkResult.context_id)
            .filter(BenchmarkResult.run_id == run_id)
            .distinct()
            .subquery()
        )
        history = history.join(
            these_cases_and_contexts,
            s.and_(
                these_cases_and_contexts.c.case_id == BenchmarkResult.case_id,
                these_cases_and_contexts.c.context_id == BenchmarkResult.context_id,
            ),
        )

    history = _add_rolling_stats_columns_to_history_query(
        history.subquery(), include_current_commit_in_rolling_stats=True
    )

    # Select the latest rolling_mean/rolling_stddev for each distribution
    latest_commits = (
        Session.query(
            history.c.case_id,
            history.c.context_id,
            s.func.max(history.c.commit_rank).label("max_commit_rank"),
        )
        .group_by(history.c.case_id, history.c.context_id)
        .subquery()
    )

    stats = (
        Session.query(
            history.c.case_id,
            history.c.context_id,
            # If we have multiple BenchmarkResults on one commit, they'll all have the
            # same rolling_mean/rolling_stddev, so just select one of them
            s.func.max(history.c.rolling_mean).label("dist_mean"),
            s.func.max(history.c.rolling_stddev).label("dist_stddev"),
        )
        .select_from(history)
        .join(
            latest_commits,
            s.and_(
                latest_commits.c.case_id == history.c.case_id,
                latest_commits.c.context_id == history.c.context_id,
                latest_commits.c.max_commit_rank == history.c.commit_rank,
            ),
        )
        .group_by(history.c.case_id, history.c.context_id)
        .all()
    )

    return {
        (row.case_id, row.context_id): (row.dist_mean, row.dist_stddev) for row in stats
    }


def _add_rolling_stats_columns_to_history_query(
    query: s.sql.Subquery, include_current_commit_in_rolling_stats: bool
) -> s.sql.Subquery:
    """Add columns with rolling statistical information to a query of BenchmarkResults
    that represents historical data we're interested in.

    The input subquery must already have the following columns:

        - BenchmarkResult.case_id
        - BenchmarkResult.context_id
        - BenchmarkResult.change_annotations
        - BenchmarkResult.mean
        - Hardware.hash
        - Commit.repository
        - Commit.timestamp

    and this function will add these columns (more detail below):

        - begins_distribution_change (non-null bool, cleaned from change_annotations)
        - commit_rank
        - segment_id
        - rolling_mean_excluding_this_commit
        - rolling_mean
        - residual
        - rolling_stddev

    Let a "segment" of the matching BenchmarkResults be defined as all BenchmarkResults
    between two BenchmarkResults where ``begins_distribution_change`` is True (inclusive
    on the left, exclusive on the right). The notable stats of the distribution include:

        - ``rolling_mean`` - the rolling mean of the current segment (calculated using
          the mean of each BenchmarkResult). The maximum size of the window is
          ``Config.DISTRIBUTION_COMMITS`` (default 100 commits), but the left side of
          the window never goes beyond the start of the segment.
        - ``residual`` - the difference of the current BenchmarkResult's mean from the
          rolling mean.
        - ``rolling_stddev`` - the rolling standard deviation of the residuals. The
          maximum size of this window is also ``Config.DISTRIBUTION_COMMITS``, but it
          *can* go beyond the start of the segment, because we assume the spread of the
          distribution does not change enough among distributions to warrant throwing
          out data from older distributions.

    If ``include_current_commit_in_rolling_stats`` is True, when calculating
    ``rolling_mean`` and ``rolling_stddev``, the window will be inclusive on the right
    side. This is useful if you need to know the rolling stats as of each commit.

    If ``include_current_commit_in_rolling_stats`` is False, the window will be
    exclusive on the right side. This is useful if you want to compare each commit to
    the previous commit's rolling stats.
    """
    # Define window ranges based on the server configuration
    range_excluding_current_commit = (-Config.DISTRIBUTION_COMMITS, -1)
    range_including_current_commit = (-Config.DISTRIBUTION_COMMITS + 1, 0)

    # Clean up a few columns so they're more usable
    query = Session.query(
        query,
        # Clean up begins_distribution_change so it's a non-null boolean column
        s.func.coalesce(
            query.c.change_annotations["begins_distribution_change"].as_boolean(),
            False,
        ).label("begins_distribution_change"),
        # When we do rolling calculations, we want to roll over commits (not individual
        # BenchmarkResults, since there may be multiple of those on one commit). Create
        # a column that represents the commit order so we can roll over that.
        s.func.dense_rank().over(order_by=query.c.timestamp).label("commit_rank"),
    ).subquery()

    # Add column with cumulative sum of distribution changes, to identify the segment
    query = Session.query(
        query,
        s.func.sum(query.c.begins_distribution_change.cast(s.Integer))
        .over(
            partition_by=(
                query.c.case_id,
                query.c.context_id,
                query.c.hash,
                query.c.repository,
            ),
            order_by=query.c.commit_rank,
        )
        .label("segment_id"),
    ).subquery()

    # Add column with rolling mean of the means (only inside of the segment)
    query = Session.query(
        query,
        s.func.coalesce(
            s.func.avg(query.c.mean).over(
                partition_by=(
                    query.c.case_id,
                    query.c.context_id,
                    query.c.hash,
                    query.c.repository,
                    query.c.segment_id,
                ),
                order_by=query.c.commit_rank,
                # Exclude the current commit first...
                range_=range_excluding_current_commit,
            ),
            query.c.mean,
        ).label("rolling_mean_excluding_this_commit"),
    ).subquery()

    # ...but if requested, include the current commit
    if include_current_commit_in_rolling_stats:
        query = Session.query(
            query,
            s.func.avg(query.c.mean)
            .over(
                partition_by=(
                    query.c.case_id,
                    query.c.context_id,
                    query.c.hash,
                    query.c.repository,
                    query.c.segment_id,
                ),
                order_by=query.c.commit_rank,
                range_=range_including_current_commit,
            )
            .label("rolling_mean"),
        ).subquery()
    else:
        query = Session.query(
            query, query.c.rolling_mean_excluding_this_commit.label("rolling_mean")
        ).subquery()

    # Add column with the residuals from the exclusive rolling mean, since we always
    # want to compare to the baseline distribution
    query = Session.query(
        query,
        (query.c.mean - query.c.rolling_mean_excluding_this_commit).label("residual"),
    ).subquery()

    # Add column with the rolling standard deviation of the residuals
    # (these can go outside the segment since we assume they don't change much)
    query = Session.query(
        query,
        s.func.stddev(query.c.residual)
        .over(
            partition_by=(
                query.c.case_id,
                query.c.context_id,
                query.c.hash,
                query.c.repository,
                # not by segment
            ),
            order_by=query.c.commit_rank,
            range_=range_including_current_commit
            if include_current_commit_in_rolling_stats
            else range_excluding_current_commit,
        )
        .label("rolling_stddev"),
    ).subquery()

    return query


def _calculate_z_score(
    data_point: Optional[float],
    unit: str,
    dist_mean: Optional[float],
    dist_stddev: Optional[float],
) -> Optional[float]:
    """Calculate the z-score of a data point compared to a distribution."""
    if (
        data_point is not None
        and dist_mean is not None
        and dist_stddev is not None
        and dist_stddev != 0
    ):
        z_score = (data_point - dist_mean) / dist_stddev
    else:
        z_score = None

    if z_score and _less_is_better(unit):
        z_score = z_score * -1

    return z_score
