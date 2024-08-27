import copy
import dataclasses
import datetime
import decimal
import logging
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union, cast

import numpy as np
import pandas as pd
import sqlalchemy as s

import conbench.units
from conbench.dbsession import current_session
from conbench.types import TBenchmarkName, THistFingerprint

from ..config import Config
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import CantFindAncestorCommitsError, Commit
from ..entities.hardware import Hardware

log = logging.getLogger(__name__)


def _to_float_or_none(
    number: Optional[Union[decimal.Decimal, float, int]]
) -> Optional[float]:
    """
    Standardize decimals/floats/ints/Nones/NaNs to be either floats or Nones

    Notes for why this can be helpful:

    - In mypy, passing an int where a float is demanded is never an error. That
      is, `if isinstance(value, float)` may be stricter than type checking,
      which can lead to bugs.
    - math.nan must be checked for with math.isnan, but it must not be given
      str or None arg, i.e. the isnan() check must be preceded by other checks.
    """
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


@dataclasses.dataclass
class HistorySampleZscoreStats:
    begins_distribution_change: bool
    segment_id: str
    rolling_mean_excluding_this_commit: float
    rolling_mean: Optional[float]
    residual: float
    rolling_stddev: float
    is_outlier: bool


# Note(JP): It stands to reason that we should move away from HistorySample to
# BMRTBenchmarkResult -- it's the ~third iteration for this kind of thing, and
# I think BMRTBenchmarkResult has nicer/more complete logic, better interface.
# E.g. `data` -> result.measurements.
@dataclasses.dataclass
class HistorySample:
    benchmark_result_id: str
    benchmark_name: TBenchmarkName
    history_fingerprint: THistFingerprint
    case_text_id: str
    case_id: str
    context_id: str
    # Is this `mean` really optional? When would this be None? this is
    # populated from BenchmarkResult.mean which is nullable. It would be a
    # major simplification if we knew that this is never None. Depends on the
    # logic in BenchmarkResult.create() which is quite intransparent today,
    # also there is a lack of spec
    mean: Optional[float]
    # Experimental: introduce 'singe value summary' concept. An item in history
    # reflects a benchmark result, and that must have a single value
    # representation for plotting and analysis. If it does not have that, it is
    # "failed" and it should not be part of history (this cannot be None).
    # Initially, this is equivalent to mean. For consumers to make sense of
    # this, also add a string field carrying the name. the name of this.
    svs: float
    # A string reflecting the kind/type/method of the SVS. E.g. "mean".
    svs_type: str
    # math.nan is allowed for representing a failed iteration.
    data: List[float]
    times: List[float]
    # TODO: make this type TUnit
    unit: str
    hardware_hash: str
    repository: str
    commit_hash: str
    commit_msg: str
    # tz-naive timestamp of commit authoring time (to be interpreted in UTC
    # timezone).
    commit_timestamp: datetime.datetime
    result_timestamp: datetime.datetime
    run_name: str
    run_tags: Dict[str, str]
    zscorestats: HistorySampleZscoreStats

    # Note(JP):
    # we should expose the unit of `data` in this structure, too.

    def __str__(self):
        return f"<{self.__class__.__name__}(mean:{self.mean}),data:{self.data}>"

    def _dict_for_api_json(self) -> dict:
        d = dataclasses.asdict(self)
        # if performance is a concern then https://pypi.org/project/orjson/
        # promises to be among the fastest for serializing python dataclass
        # instances into JSON.

        # For external consumption, change type/representation of time.
        d["commit_timestamp"] = self.commit_timestamp.isoformat()
        d["result_timestamp"] = self.result_timestamp.isoformat()

        # Rename SVS for clarity for external consumption.
        d["single_value_summary"] = d.pop("svs")
        d["single_value_summary_type"] = d.pop("svs_type")

        # Remove new props for now (needs test suite adjustment, and so far
        # usage of new props is internal).
        d.pop("benchmark_name")
        d.pop("case_text_id")
        return d


def get_history_for_benchmark(benchmark_result_id: str) -> List[HistorySample]:
    # First, find the history fingerprint based on the input benchmark result ID. This
    # database lookup may raise the `NotFound` exception.

    result: BenchmarkResult = BenchmarkResult.one(id=benchmark_result_id)

    benchmark_name = cast(TBenchmarkName, str(result.case.name))

    return get_history_for_fingerprint(
        result.history_fingerprint,
        # this is technically represented in the fingerprint, but we want to explicitly
        # store the benchmark name on the resulting objects
        benchmark_name,
    )


def get_history_for_fingerprint(
    history_fingerprint: THistFingerprint, benchmark_name: TBenchmarkName
) -> List[HistorySample]:
    """
    Given a history fingerprint, return all non-errored BenchmarkResults (past, present,
    and future) on the default branch that match it, along with information about the
    stats of the distribution as of each BenchmarkResult. Order is not guaranteed. Used
    to power the history API, which also powers the timeseries plots.

    For further detail on the stats columns, see the docs of
    ``_add_rolling_stats_columns_to_history_query()``.
    """
    history = (
        current_session.query(
            BenchmarkResult,
            Hardware.hash.label("hardware_hash"),
            Commit.sha.label("commit_hash"),
            Commit.repository,
            Commit.message.label("commit_message"),
            Commit.timestamp.label("commit_timestamp"),
            BenchmarkResult.run_tags["name"].label("run_name"),
        )
        .join(Hardware, Hardware.id == BenchmarkResult.hardware_id)
        # This is an inner join, so results that aren't associated with a particular
        # commit are excluded from the result. That's okay because we only want
        # default-branch results anyway.
        .join(Commit, Commit.id == BenchmarkResult.commit_id)
        .filter(
            BenchmarkResult.error.is_(None),
            BenchmarkResult.history_fingerprint == history_fingerprint,
            # Today this is equivalent to "is on default branch". Note this excludes any
            # "unknown context" commits, where the repo/hash are known but metadata
            # retrieval from the GitHub API failed.
            Commit.sha == Commit.fork_point_sha,
        )
    )

    history_df, bmrs_by_bmrid = execute_history_query_get_dataframe(history.statement)

    if len(history_df) == 0:
        return []

    history_df_rolling_stats = _add_rolling_stats_columns_to_df(
        history_df, include_current_commit_in_rolling_stats=False
    )

    samples: List[HistorySample] = []

    # Iterate over rows of pandas dataframe; get each row as namedtuple.
    for sample in history_df_rolling_stats.itertuples():
        # Note(JP): the Commit.timestamp is nullable, i.e. not all Commit
        # entities in the DB have a timestamp (authoring time) attached.
        # However, in this function I believe there is an invariant that the
        # query only returns Commits that we have this metadata for (what's the
        # precise reason for this invariant? I think there is one). Codify this
        # invariant with an assertion.
        assert isinstance(sample.timestamp, datetime.datetime)

        # Restore 'sample' (df row) correspondence to BenchmarkResult objects.
        result = bmrs_by_bmrid[sample.benchmark_result_id]

        zstats = HistorySampleZscoreStats(
            begins_distribution_change=sample.begins_distribution_change,
            segment_id=sample.segment_id,
            rolling_mean_excluding_this_commit=sample.rolling_mean_excluding_this_commit,
            rolling_mean=_to_float_or_none(sample.rolling_mean),
            residual=sample.residual,
            rolling_stddev=_to_float_or_none(sample.rolling_stddev) or 0.0,
            is_outlier=sample.is_outlier or False,
        )

        # For both, `sample.data` and `sample.times`, expect either None or a
        # list. Make it so that in the output object they are always a list,
        # potentially empty. `data` and `times` contain more than one value if
        # this was a multi-sample benchmark.
        data = []
        if result.data is not None:
            data = [float(d) if d is not None else math.nan for d in result.data]

        times = []
        if result.times is not None:
            times = [float(t) if t is not None else math.nan for t in result.times]

        samples.append(
            HistorySample(
                benchmark_result_id=sample.benchmark_result_id,
                benchmark_name=benchmark_name,
                history_fingerprint=history_fingerprint,
                case_id=result.case_id,
                case_text_id=result.case.text_id,
                context_id=result.context_id,
                mean=_to_float_or_none(result.mean),
                svs=result.svs,
                svs_type=result.svs_type,
                data=data,
                times=times,
                # JSON schema requires unit to be set upon BMR insertion, so I
                # do not think this 'undefined' is met often. Maybe empty
                # strings can be inserted into the DB, and this would be
                # handled here, too.
                unit=result.unit if result.unit else "undefined",
                hardware_hash=sample.hash,
                repository=sample.repository,
                commit_msg=sample.commit_message,
                commit_hash=sample.commit_hash,
                commit_timestamp=sample.timestamp,
                result_timestamp=sample.result_timestamp,
                run_name=sample.run_name,
                run_tags=sample.run_tags,
                zscorestats=zstats,
            )
        )

    return samples


def set_z_scores(
    contender_benchmark_results: List[BenchmarkResult],
    baseline_commit: Commit,
    history_fingerprints: List[THistFingerprint],
):
    """Set the "z_score" attribute on each contender BenchmarkResult, comparing it to
    the baseline distribution of BenchmarkResults that share the same history
    fingerprint, in the git ancestry of the baseline_commit (inclusive).

    The given contender_benchmark_results must all have the same run_id, which implies
    that they share the same hardware, repository, and commit. But they may have
    different names, cases, and/or contexts, so they may have different history
    fingerprints. To save time, provide those fingerprints in the history_fingerprints
    argument.

    This function does not affect the database whatsoever. It only populates an
    attribute on the given python objects. This is typically called right before
    returning a jsonify-ed response from the API, so the "z_score" attribute shouldn't
    already be set, but if it is already set, it will be silently overwritten.

    Should not raise anything, except a ValueError if there are mixed run_ids provided.
    If we can't find a z-score for some reason, the z_score attribute will be None on
    that BenchmarkResult.
    """
    distribution_stats = _query_and_calculate_distribution_stats(
        baseline_commit=baseline_commit, history_fingerprints=history_fingerprints
    )

    for benchmark_result in contender_benchmark_results:
        dist_mean, dist_stddev = distribution_stats.get(
            benchmark_result.history_fingerprint, (None, None)
        )
        benchmark_result.z_score = _calculate_z_score(
            data_point=_to_float_or_none(benchmark_result.svs),
            unit=benchmark_result.unit,
            dist_mean=_to_float_or_none(dist_mean),
            dist_stddev=_to_float_or_none(dist_stddev),
        )


def _query_and_calculate_distribution_stats(
    baseline_commit: Commit, history_fingerprints: List[THistFingerprint]
) -> Dict[THistFingerprint, Tuple[Optional[float], Optional[float]]]:
    """Query and calculate rolling stats of the distribution of all BenchmarkResults
    that:

    - are associated with any of the last DISTRIBUTION_COMMITS commits in the
      baseline_commit's git ancestry (inclusive)
    - have no errors

    The calculations are grouped by history fingerprint, returning a dict that looks
    like:

    ``{history_fingerprint: (dist_mean, dist_stddev)}``

    Only do the calculation for the given history_fingerprints.

    For further detail on the stats columns, see the docs of
    ``_add_rolling_stats_columns_to_df()``.
    """
    try:
        commit_ancestry_query = baseline_commit.commit_ancestry_query.order_by(
            s.desc("commit_order")
        ).limit(Config.DISTRIBUTION_COMMITS)
    except CantFindAncestorCommitsError as e:
        log.debug(f"Couldn't _query_and_calculate_distribution_stats() because {e}")
        return {}

    commit_ancestry_info = commit_ancestry_query.all()
    commit_timestamps_by_id = {
        row.ancestor_id: row.ancestor_timestamp for row in commit_ancestry_info
    }

    # Note[austin]: Okay. Pros and cons here. This is not DRY, so we have to maintain
    # this logic in addition to the SVS logic in benchmark_result.py. Also, the SVS is
    # not exactly equivalent to the mean/min/max in all cases because of "errored
    # results", and that's especially true if we change the default definition of SVS in
    # the future (in which case let's revisit this!). But after careful analysis of the
    # code, I believe that they are equivalent for BenchmarkResults where error is None
    # and mean/min/max is not None, at least since #1127 or previous.
    #
    # The benefit of this assumption is we can avoid the time-consuming
    # execute_history_query_get_dataframe() for-loops and SQLAlchemy object
    # instantiation for big data (3e5 results). This goes SO MUCH faster.
    if Config.SVS_TYPE == "mean":
        svs_col = BenchmarkResult.mean
    elif Config.SVS_TYPE == "best":
        # Right now less is always better unless the unit is "per second", so return the
        # max in that case and the min otherwise.
        # Also, the min/max fields are missing when there's less than 3 reps, so
        # calculate those on the fly in that case.
        data_len = s.func.array_length(BenchmarkResult.data, 1)
        more_is_better = BenchmarkResult.unit.like("%/s")

        svs_col = s.case(
            (data_len == 1, BenchmarkResult.mean),
            (
                s.and_(data_len == 2, more_is_better),
                s.func.greatest(BenchmarkResult.data[1], BenchmarkResult.data[2]),
            ),
            (
                s.and_(data_len == 2, ~more_is_better),
                s.func.least(BenchmarkResult.data[1], BenchmarkResult.data[2]),
            ),
            (more_is_better, BenchmarkResult.max),
            else_=BenchmarkResult.min,
        )  # type: ignore
    else:
        raise ValueError("server is not configured properly")

    # Find all historic results in the distribution to analyze.
    history = s.select(
        BenchmarkResult.commit_id,
        BenchmarkResult.history_fingerprint,
        BenchmarkResult.timestamp.label("result_timestamp"),
        BenchmarkResult.change_annotations,
        svs_col.label("svs"),
    ).filter(
        BenchmarkResult.error.is_(None),
        BenchmarkResult.mean.is_not(None),
        BenchmarkResult.unit.is_not(None),
        BenchmarkResult.commit_id.in_(commit_timestamps_by_id.keys()),
        BenchmarkResult.history_fingerprint.in_(history_fingerprints),
    )

    history_df = pd.read_sql(history, current_session.connection())
    history_df["timestamp"] = history_df["commit_id"].map(commit_timestamps_by_id)

    if len(history_df) == 0:
        return {}

    history_df = _add_rolling_stats_columns_to_df(
        history_df, include_current_commit_in_rolling_stats=True
    )

    # Select the latest rolling_mean/rolling_stddev for each history_fingerprint
    stats_df = history_df.sort_values("timestamp", ascending=False).drop_duplicates(
        ["history_fingerprint"]
    )

    return {
        row.history_fingerprint: (row.rolling_mean, row.rolling_stddev)
        for row in stats_df.itertuples()
    }


def execute_history_query_get_dataframe(statement) -> Tuple[pd.DataFrame, Dict]:
    """
    Emit prepared query statement to database.

    Return a (df, dict) tuple. In the pandas DataFrame, each row represents a
    benchmark result (BMR) plus associated metadata (that cannot be typically
    found on the BenchmarkResult directly).

    A row in the dataframe contains limited information about a BMR, such as
    its ID. The dictionary mapping allows for looking up the full BMR via ID.

    Think: this function returns a timeseries: one BenchmarkResult(+additional
    info) per point in time, and the `BenchmarkResult(+additional info)` is
    spread across two objects.

    Note: this can be called on a query that returns results from multiple history
    fingerprints (hence grouping would be necessary later on when further processing
    this).

    Previously, we did

        df = pd.read_sql(statement, current_session.connection())

    which unpacked individual BenchmarkResult columns into dataframe columns.

    It was not easily possible to access the raw BenchmarkResult object.

    This paradigm here does more explicit iteration and creates more
    intermediate objects, but also allows for more explicitly mapping items
    into the dataframe.

    If this fetches too many BMR columns, we can limit the columns fetched
    actively with a "deferred loading" technique provided by SQLAlchemy.

    Note that `row_iterator ` is an iterator that can only be consumed once,
    i.e. we immediately store the data in mappings.

    Assume that history is not gigantic; and even when history is comprised of
    O(1000) benchmark results then the two dictionaries and the one dataframe
    creates in this function should be smallish (from a mem consumption point
    of view).
    """
    row_iterator = current_session.execute(statement)
    rows_by_bmrid = {}
    bmrs_by_bmrid: Dict[str, BenchmarkResult] = {}

    for row in row_iterator:
        bmr = row[0]
        rows_by_bmrid[bmr.id] = row
        bmrs_by_bmrid[bmr.id] = bmr

    if len(rows_by_bmrid) == 0:
        log.debug("history query returned no results")
        return pd.DataFrame({}), {}

    # The dictionary from which a pandas DataFrame will be be created.
    dict_for_df = defaultdict(list)

    # Translate row-oriented result into column-oriented df, but picking only
    # specific columns.
    for bmr_id, row in rows_by_bmrid.items():
        # Iterate over values in this row, and also get their metadata/column
        # descriptions. See
        # https://stackoverflow.com/a/6456360/145400
        for coldesc, value in zip(statement.column_descriptions, row):
            if coldesc["name"] == "BenchmarkResult":
                assert bmr_id == value.id
                dict_for_df["benchmark_result_id"].append(bmr_id)
                dict_for_df["case_id"].append(value.case_id)
                dict_for_df["context_id"].append(value.context_id)
                # dict_for_df["mean"].append(value.mean)
                dict_for_df["svs"].append(value.svs)
                dict_for_df["change_annotations"].append(value.change_annotations)
                dict_for_df["result_timestamp"].append(value.timestamp)
                dict_for_df["history_fingerprint"].append(value.history_fingerprint)
                dict_for_df["run_tags"].append(value.run_tags)
            if coldesc["name"] == "hardware_hash":
                dict_for_df["hash"].append(value)

            if coldesc["name"] == "repository":
                dict_for_df["repository"].append(value)

            if coldesc["name"] == "commit_timestamp":
                # The timestamp we associate with this benchmark result for
                # timeseries analysis. This is chosen to be the commit
                # timestamp.
                dict_for_df["timestamp"].append(value)

            # This does not need to be in the dataframe, but it's better
            # than result.commit.message below
            if coldesc["name"] in ("commit_message", "commit_hash", "run_name"):
                dict_for_df[coldesc["name"]].append(value)

    history_df = pd.DataFrame(dict_for_df)
    # log.info("df:\n%s", history_df.to_string())

    return history_df, bmrs_by_bmrid


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

        - BenchmarkResult: history_fingerprint
        - BenchmarkResult: change_annotations
        - BenchmarkResult: svs (single value summary)
        - BenchmarkResult: result_timestamp
        - Commit: timestamp

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
        ["history_fingerprint", "timestamp"], inplace=True, ignore_index=True
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
        df.groupby(["history_fingerprint"])
        .rolling(
            _CommitIndexer(window_size=len(df) + 1),
            on="timestamp",
            closed="right",
            min_periods=1,
        )["begins_distribution_change"]
        .sum()
        .values
    )

    # Add column with rolling mean of the SVSs (only inside of the segment)
    df.loc[~df.is_outlier, "rolling_mean_excluding_this_commit"] = (
        df.loc[~df.is_outlier]
        .groupby(["history_fingerprint", "segment_id"])
        .rolling(
            _CommitIndexer(window_size=Config.DISTRIBUTION_COMMITS),
            on="timestamp",
            # Exclude the current commit first...
            closed="left",
            min_periods=1,
        )["svs"]
        .mean()
        .values
    )
    # (and fill NaNs at the beginning of segments with the first value)
    df.loc[~df.is_outlier, "rolling_mean_excluding_this_commit"] = df.loc[
        ~df.is_outlier, "rolling_mean_excluding_this_commit"
    ].combine_first(df.loc[~df.is_outlier, "svs"])

    # ...but if requested, include the current commit
    if include_current_commit_in_rolling_stats:
        df.loc[~df.is_outlier, "rolling_mean"] = (
            df.loc[~df.is_outlier]
            .groupby(["history_fingerprint", "segment_id"])
            .rolling(
                _CommitIndexer(window_size=Config.DISTRIBUTION_COMMITS),
                on="timestamp",
                closed="right",
                min_periods=1,
            )["svs"]
            .mean()
            .values
        )
    else:
        df["rolling_mean"] = df["rolling_mean_excluding_this_commit"]

    # Add column with the residuals from the exclusive rolling mean, since we always
    # want to compare to the baseline distribution
    df["residual"] = df["svs"] - df["rolling_mean_excluding_this_commit"]

    # Add column with the rolling standard deviation of the residuals
    # (these can go outside the segment since we assume they don't change much)
    df.loc[~df.is_outlier, "rolling_stddev"] = (
        df.loc[~df.is_outlier]
        .groupby(["history_fingerprint"])  # not segment
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
        return None

    # Note(JP): can `unit` here be `None`, really? That should not be the case.
    # A z-score calculation requires the happy path.
    assert unit is not None
    us = conbench.units.legacy_convert(unit)
    if z_score and conbench.units.less_is_better(us):
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
        ["history_fingerprint", "timestamp", "result_timestamp"],
        inplace=True,
        ignore_index=True,
    )

    # split / apply
    out_group_df_list = []
    for _, group_df in tmp_df.groupby(["history_fingerprint"]):
        # clean copy will only get result columns
        out_group_df = copy.deepcopy(group_df)

        group_df["svs_diff"] = group_df["svs"].diff()
        svs_diff_clipped = copy.deepcopy(group_df.svs_diff)
        svs_diff_clipped.loc[
            (group_df.svs_diff < group_df.svs_diff.quantile(0.05))
            | (group_df.svs_diff > group_df.svs_diff.quantile(0.95))
        ] = np.nan
        group_df["rolling_mean"] = svs_diff_clipped.rolling(
            Config.DISTRIBUTION_COMMITS, min_periods=1
        ).mean()
        group_df["rolling_std"] = svs_diff_clipped.rolling(
            Config.DISTRIBUTION_COMMITS, min_periods=1
        ).std()
        group_df["z_score"] = (
            group_df.svs_diff - group_df.rolling_mean
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
