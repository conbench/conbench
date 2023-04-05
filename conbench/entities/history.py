import copy
import dataclasses
import datetime
import decimal
import logging
import math
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
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


def _to_float(number: Optional[Union[decimal.Decimal, float, int]]) -> Optional[float]:
    """Standardize decimals/floats/ints/Nones/NaNs to be either floats or Nones"""
    if number is None:
        return None

    number = float(number)
    if math.isnan(number):
        return None

    return number


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

        return {
            "benchmark_id": history.id,
            "case_id": history.case_id,
            "context_id": history.context_id,
            "mean": _to_float(history.mean),
            "data": history.data,
            "times": history.times,
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
            "distribution_mean": _to_float(history.rolling_mean),
            "distribution_stdev": _to_float(history.rolling_stddev) or 0.0,
        }


class HistorySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


@dataclasses.dataclass
class HistorySampleZscoreStats:
    begins_distribution_change: bool
    segment_id: str
    rolling_mean_excluding_this_commit: float
    rolling_mean: Optional[float]
    residual: float
    rolling_stddev: float
    is_outlier: bool


@dataclasses.dataclass
class HistorySample:
    benchmark_result_id: str
    case_id: str
    context_id: str
    # Is this `mean` really optional? When would this be None? this is
    # populated from BenchmarkResult.mean which is nullable. It would be a
    # major simplification if we knew that this is never None. Depends on the
    # logic in BenchmarkResult.create() which is quite intransparent today,
    # also there is a lack of spec
    mean: Optional[float]
    # math.nan is allowed for representing a failed iteration.
    data: List[float]
    times: List[float]
    unit: str
    hardware_hash: str
    repository: str
    commit_hash: str
    commit_msg: str
    # tz-naive timestamp of commit authoring time (to be interpreted in UTC
    # timezone).
    commit_timestamp: datetime.datetime
    run_name: str
    zscorestats: HistorySampleZscoreStats

    def _dict_for_api_json(self) -> dict:
        d = dataclasses.asdict(self)
        # if performance is a concern then https://pypi.org/project/orjson/
        # promises to be among the fastest for serializing python dataclass
        # instances into JSON.
        d["commit_timestamp"] = self.commit_timestamp.isoformat()
        return d


def get_history_for_benchmark(benchmark_result_id: str):
    # First, find case / context / hardware / repo combination based on the
    # input benchmark result ID. This database lookup may raise the `NotFound`
    # exception.

    benchmark_result: BenchmarkResult = BenchmarkResult.one(id=benchmark_result_id)
    return get_history_for_cchr(
        benchmark_result.case_id,
        benchmark_result.context_id,
        benchmark_result.run.hardware.hash,
        benchmark_result.run.commit.repository,
    )


def get_history_for_cchr(
    case_id: str, context_id: str, hardware_hash: str, repo: str
) -> List[HistorySample]:
    """
    Given a case/context/hardware/repo, return all non-errored BenchmarkResults
    (past, present, and future) on the default branch that match those
    criteria, along with information about the stats of the distribution as of
    each BenchmarkResult. Order is not guaranteed. Used to power the history
    API, which also powers the timeseries plots.

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
            BenchmarkResult.timestamp.label("result_timestamp"),
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
    )

    history_df = pd.read_sql(history.statement, Session.connection())

    history_df = _add_rolling_stats_columns_to_df(
        history_df, include_current_commit_in_rolling_stats=False
    )

    # return list(history_df.itertuples())

    samples: List[HistorySample] = []
    # Iterate over rows of pandas dataframe; get each row as namedtuple.
    for sample in history_df.itertuples():
        # Note(JP): the Commit.timestamp is nullable, i.e. not all Commit
        # entities in the DB have a timestamp (authoring time) attached.
        # However, in this function I believe there is an invariant that the
        # query only returns Commits that we have this metadata for (what's the
        # precise reason for this invariant? I think there is one). Codify this
        # invariant with an assertion.
        assert isinstance(sample.timestamp, datetime.datetime)

        zstats = HistorySampleZscoreStats(
            begins_distribution_change=sample.begins_distribution_change,
            segment_id=sample.segment_id,
            rolling_mean_excluding_this_commit=sample.rolling_mean_excluding_this_commit,
            rolling_mean=_to_float(sample.rolling_mean),
            residual=sample.residual,
            rolling_stddev=_to_float(sample.rolling_stddev) or 0.0,
            is_outlier=sample.is_outlier or False,
        )

        # For both, `sample.data` and `sample.times`, expect either None or a
        # list. Make it so that in the output object they are always a list,
        # potentially empty. `data` and `times` contain more than one value if
        # this was a multi-sample benchmark.

        data = []
        if sample.data is not None:
            data = [float(d) if d is not None else math.nan for d in sample.data]

        times = []
        if sample.times is not None:
            times = [float(t) if t is not None else math.nan for t in sample.times]

        samples.append(
            HistorySample(
                benchmark_result_id=sample.id,
                case_id=sample.case_id,
                context_id=sample.context_id,
                mean=sample.mean,
                data=data,
                times=times,
                unit=sample.unit,
                hardware_hash=sample.hash,
                repository=sample.repository,
                commit_msg=sample.message,
                commit_hash=sample.sha,
                commit_timestamp=sample.timestamp,
                run_name=sample.name,
                zscorestats=zstats,
            )
        )

    return samples


def set_z_scores(
    contender_benchmark_results: List[BenchmarkResult], baseline_commit: Commit
):
    """Set the "z_score" attribute on each contender BenchmarkResult, comparing it to
    the baseline distribution of BenchmarkResults that share the same
    case/context/hardware/repo, in the git ancestry of the baseline_commit (inclusive).

    The given contender_benchmark_results must all have the same run_id.

    This function does not affect the database whatsoever. It only populates an
    attribute on the given python objects. This is typically called right before
    returning a jsonify-ed response from the API, so the "z_score" attribute shouldn't
    already be set, but if it is already set, it will be silently overwritten.

    Should not raise anything, except a ValueError if there are mixed run_ids provided.
    If we can't find a z-score for some reason, the z_score attribute will be None on
    that BenchmarkResult.
    """
    contender_run_ids = set(result.run_id for result in contender_benchmark_results)
    if len(contender_run_ids) != 1:
        raise ValueError(
            f"Encountered mixed run_ids in set_z_scores(): {contender_run_ids}"
        )
    contender_run_id = contender_run_ids.pop()

    if len(contender_benchmark_results) == 1:
        # performance optimization
        case_id = contender_benchmark_results[0].case_id
        context_id = contender_benchmark_results[0].context_id
    else:
        case_id = None
        context_id = None

    distribution_stats = _query_and_calculate_distribution_stats(
        contender_run_id=contender_run_id,
        baseline_commit=baseline_commit,
        case_id=case_id,
        context_id=context_id,
    )

    for benchmark_result in contender_benchmark_results:
        dist_mean, dist_stddev = distribution_stats.get(
            (benchmark_result.case_id, benchmark_result.context_id), (None, None)
        )
        benchmark_result.z_score = _calculate_z_score(
            data_point=_to_float(benchmark_result.mean),
            unit=benchmark_result.unit,
            dist_mean=_to_float(dist_mean),
            dist_stddev=_to_float(dist_stddev),
        )


def _query_and_calculate_distribution_stats(
    contender_run_id: str,
    baseline_commit: Commit,
    case_id: Optional[str],
    context_id: Optional[str],
) -> Dict[Tuple[str, str], Tuple[Optional[float], Optional[float]]]:
    """Query and calculate rolling stats of the distribution of all BenchmarkResults
    that:

    - are associated with any of the last DISTRIBUTION_COMMITS commits in the
      baseline_commit's git ancestry (inclusive)
    - match the contender run's hardware
    - have no errors

    The calculations are grouped by case and context, returning a dict that looks like:

    ``{(case_id, context_id): (dist_mean, dist_stddev)}``

    If case_id and context_id are not given, return all case/context pairs that the
    contender run has results for. This saves some time compared to returning all
    case/context pairs in the database.

    If case_id and context_id are given, only return that pair. This saves a lot of
    time.

    For further detail on the stats columns, see the docs of
    ``_add_rolling_stats_columns_to_df()``.
    """
    contender_run = Run.get(contender_run_id)

    try:
        commits = baseline_commit.commit_ancestry_query.subquery()
    except CantFindAncestorCommitsError as e:
        log.debug(f"Couldn't _query_and_calculate_distribution_stats() because {e}")
        return {}

    # Get the last DISTRIBUTION_COMMITS ancestor commits of the baseline commit
    commits = (
        Session.query(commits)
        .order_by(commits.c.commit_order.desc())
        .limit(Config.DISTRIBUTION_COMMITS)
        .subquery()
    )

    # Find all historic results in the distribution to analyze
    history = (
        Session.query(
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            BenchmarkResult.change_annotations,
            BenchmarkResult.mean,
            BenchmarkResult.timestamp.label("result_timestamp"),
            Hardware.hash,
            s.sql.expression.literal(baseline_commit.repository).label("repository"),
            commits.c.ancestor_timestamp.label("timestamp"),
        )
        .select_from(BenchmarkResult)
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(commits, commits.c.ancestor_id == Run.commit_id)
        .filter(
            BenchmarkResult.error.is_(None),
            Hardware.hash == contender_run.hardware.hash,
        )
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
            .filter(BenchmarkResult.run_id == contender_run_id)
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

    history_df = pd.read_sql(history.statement, Session.connection())

    history_df = _add_rolling_stats_columns_to_df(
        history_df, include_current_commit_in_rolling_stats=True
    )

    # Select the latest rolling_mean/rolling_stddev for each distribution
    stats_df = history_df.sort_values("timestamp", ascending=False).drop_duplicates(
        ["case_id", "context_id"]
    )
    return {
        (row.case_id, row.context_id): (row.rolling_mean, row.rolling_stddev)
        for row in stats_df.itertuples()
    }


class _CommitIndexer(pd.api.indexers.BaseIndexer):
    """pandas isn't great about rolling over ranges, so this class lets us roll over
    the commit timestamp column correctly (not caring about time between commits)."""

    def get_window_bounds(
        self,
        num_values: int = 0,
        min_periods: Optional[int] = None,
        center: Optional[bool] = None,
        closed: Optional[str] = None,
        step: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return numpy arrays of the respective start and end indexes of all rolling
        windows for this slice of commit timestamps.
        """
        # self.index_array is the (sorted) current slice of the timestamp column,
        # converted to an int64 np array. Find the dense rank of each timestamp.
        commit_ranks = pd.Series(self.index_array).rank(method="dense").values

        # np.searchsorted() finds the indices into which values would need to be
        # inserted to maintain order. We can use that to find the indexes of the end of
        # the window (same as the current commit) and start of the window (the current
        # commit minus the window size).
        end_ixs = np.searchsorted(commit_ranks, commit_ranks, side=closed)  # type: ignore[call-overload]
        start_ixs = np.searchsorted(
            commit_ranks, commit_ranks - self.window_size, side=closed
        )  # type: ignore[call-overload]
        return start_ixs, end_ixs


def _add_rolling_stats_columns_to_df(
    df: pd.DataFrame, include_current_commit_in_rolling_stats: bool
) -> pd.DataFrame:
    """Add columns with rolling statistical information to a DataFrame of
    BenchmarkResults that represents historical data we're interested in.

    The input DataFrame must already have the following columns:

        - BenchmarkResult.case_id
        - BenchmarkResult.context_id
        - BenchmarkResult.change_annotations
        - BenchmarkResult.mean
        - BenchmarkResult.timestamp.label("result_timestamp")
        - Hardware.hash
        - Commit.repository
        - Commit.timestamp

    and this function will add these columns (more detail below):

        - begins_distribution_change (non-null bool, cleaned from change_annotations)
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
    df = _detect_shifts_with_trimmed_estimators(df=df)

    # pandas likes the data to be sorted
    df.sort_values(
        ["case_id", "context_id", "hash", "repository", "timestamp"],
        inplace=True,
        ignore_index=True,
    )

    # Clean up begins_distribution_change so it's a non-null boolean column
    df["begins_distribution_change"] = [
        bool(x.get("begins_distribution_change", False)) if x else False
        for x in df["change_annotations"]
    ]

    # NOTE(EV): If uncommented, this line will integrate manually-specified distribution
    # changes with those automatically detected. Before enabling this, we want a way for
    # users to manually remove an automatically-detected step-change.
    #
    # # Add in step changes automatically detected
    # df["begins_distribution_change"] = df["begins_distribution_change"] | df["is_step"]

    # Add column with cumulative sum of distribution changes, to identify the segment
    df["segment_id"] = (
        df.groupby(["case_id", "context_id", "hash", "repository"])
        .rolling(
            _CommitIndexer(window_size=len(df) + 1),
            on="timestamp",
            closed="right",
            min_periods=1,
        )["begins_distribution_change"]
        .sum()
        .values
    )

    # Add column with rolling mean of the means (only inside of the segment)
    df.loc[~df.is_outlier, "rolling_mean_excluding_this_commit"] = (
        df.loc[~df.is_outlier]
        .groupby(["case_id", "context_id", "hash", "repository", "segment_id"])
        .rolling(
            _CommitIndexer(window_size=Config.DISTRIBUTION_COMMITS),
            on="timestamp",
            # Exclude the current commit first...
            closed="left",
            min_periods=1,
        )["mean"]
        .mean()
        .values
    )
    # (and fill NaNs at the beginning of segments with the first value)
    df.loc[~df.is_outlier, "rolling_mean_excluding_this_commit"] = df.loc[
        ~df.is_outlier, "rolling_mean_excluding_this_commit"
    ].combine_first(df.loc[~df.is_outlier, "mean"])

    # ...but if requested, include the current commit
    if include_current_commit_in_rolling_stats:
        df.loc[~df.is_outlier, "rolling_mean"] = (
            df.loc[~df.is_outlier]
            .groupby(["case_id", "context_id", "hash", "repository", "segment_id"])
            .rolling(
                _CommitIndexer(window_size=Config.DISTRIBUTION_COMMITS),
                on="timestamp",
                closed="right",
                min_periods=1,
            )["mean"]
            .mean()
            .values
        )
    else:
        df["rolling_mean"] = df["rolling_mean_excluding_this_commit"]

    # Add column with the residuals from the exclusive rolling mean, since we always
    # want to compare to the baseline distribution
    df["residual"] = df["mean"] - df["rolling_mean_excluding_this_commit"]

    # Add column with the rolling standard deviation of the residuals
    # (these can go outside the segment since we assume they don't change much)
    df.loc[~df.is_outlier, "rolling_stddev"] = (
        df.loc[~df.is_outlier]
        .groupby(["case_id", "context_id", "hash", "repository"])  # not segment
        .rolling(
            _CommitIndexer(window_size=Config.DISTRIBUTION_COMMITS),
            on="timestamp",
            closed="right" if include_current_commit_in_rolling_stats else "left",
            min_periods=1,
        )["residual"]
        .std()
        .values
    )

    return df


def _calculate_z_score(
    data_point: Optional[float],
    unit: Optional[str],
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


def _detect_shifts_with_trimmed_estimators(
    df: pd.DataFrame, z_score_threshold=5.0
) -> pd.DataFrame:
    """Detect outliers and distribution shifts in historical data

    Uses a z-score-based detection algorithm that uses trimmed rolling means and standard
    deviations to avoid influence by outliers. Takes a dataframe of the same sort as
    `_add_rolling_stats_columns_to_df`, and returning that dataframe with two additional
    columns:

    - `is_step` (bool): Is this point the start of a new segment?
    - `is_outlier` (bool): Is this point an outlier that should be ignored?
    """
    tmp_df = copy.deepcopy(df)

    # skip computation if no history
    if df.shape[0] == 0:
        tmp_df["is_step"] = pd.Series([], dtype=bool)
        tmp_df["is_outlier"] = pd.Series([], dtype=bool)
        return tmp_df

    # pandas likes the data to be sorted
    tmp_df.sort_values(
        [
            "case_id",
            "context_id",
            "hash",
            "repository",
            "timestamp",
            "result_timestamp",
        ],
        inplace=True,
        ignore_index=True,
    )

    # split / apply
    out_group_df_list = []
    for _, group_df in tmp_df.groupby(["case_id", "context_id", "hash", "repository"]):
        # clean copy will only get result columns
        out_group_df = copy.deepcopy(group_df)

        group_df["mean_diff"] = group_df["mean"].diff()
        mean_diff_clipped = copy.deepcopy(group_df.mean_diff)
        mean_diff_clipped.loc[
            (group_df.mean_diff < group_df.mean_diff.quantile(0.05))
            | (group_df.mean_diff > group_df.mean_diff.quantile(0.95))
        ] = np.nan
        group_df["rolling_mean"] = mean_diff_clipped.rolling(
            Config.DISTRIBUTION_COMMITS, min_periods=1
        ).mean()
        group_df["rolling_std"] = mean_diff_clipped.rolling(
            Config.DISTRIBUTION_COMMITS, min_periods=1
        ).std()
        group_df["z_score"] = (
            group_df.mean_diff - group_df.rolling_mean
        ) / group_df.rolling_std

        group_df["is_shift"] = group_df.z_score.abs() > z_score_threshold
        group_df["reverts"] = group_df.is_shift & group_df.is_shift.shift(-1)
        out_group_df["is_step"] = (
            group_df.is_shift
            & ~group_df.reverts
            & ~group_df.reverts.shift(1, fill_value=False)
        )
        out_group_df["is_outlier"] = group_df.is_shift & group_df.reverts

        out_group_df_list.append(out_group_df)

    # combine
    out_df = pd.concat(out_group_df_list)

    return out_df
