import copy
import dataclasses
import datetime
import decimal
import hashlib
import logging
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union, cast

import numpy as np
import pandas as pd
import sqlalchemy as s

import conbench.units
from conbench.dbsession import current_session
from conbench.types import TBenchmarkName

from ..config import Config
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import CantFindAncestorCommitsError, Commit
from ..entities.hardware import Hardware
from ..entities.run import Run

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


# It stands to reason that we should move away from HistorySample to
# BMRTBenchmarkResult -- it's the ~third iteration for this kind of thing, and
# I think BMRTBenchmarkResult has nicer/more complete logic, better interface.
# E.g. `data` -> result.measurements.
@dataclasses.dataclass
class HistorySample:
    benchmark_result_id: str
    benchmark_name: TBenchmarkName
    ts_fingerprint: str
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

        # Rename SVS for clarity for external consumption.
        d["single_value_summary"] = d.pop("svs")
        d["single_value_summary_type"] = d.pop("svs_type")

        # Remove new props for now (needs test suite adjustment, and so far
        # usage of new props is internal).
        d.pop("ts_fingerprint")
        d.pop("benchmark_name")
        d.pop("case_text_id")
        return d


def get_history_for_benchmark(benchmark_result_id: str) -> List[HistorySample]:
    # First, find case / context / hardware / repo combination based on the
    # input benchmark result ID. This database lookup may raise the `NotFound`
    # exception.

    result: BenchmarkResult = BenchmarkResult.one(id=benchmark_result_id)

    benchmark_name = cast(TBenchmarkName, str(result.case.name))

    if result.run.commit is None:
        # Alternatively, raise an exception here -- allowing to inform the
        # user that conceptually there will never be history for this
        # benchmark result, because it's not associated with repo/commit
        # information
        return []

    return get_history_for_cchr(
        # this is technically represented in "case", but we want to explicitly
        # store the benchmark name on the resulting objects
        benchmark_name,
        result.case_id,
        result.context_id,
        result.run.hardware.hash,
        result.run.commit.repository,
    )


def get_history_for_cchr(
    benchmark_name: TBenchmarkName,
    case_id: str,
    context_id: str,
    hardware_hash: str,
    repo_url: str,
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

    # Do not support history logic for results that are not associated with
    # 'commit context'. Here, we could/should inspect `repo` to not be an empty
    # string for example (there may be stray "no context" objects in the
    # database that have the repo set to an empty string, i.e. the filter for
    # repo=="" might even yield something).

    # The goal here is to have an identifier that represents a timeseries (as
    # opposed to a single result). We may want to first-class this general
    # idea. Also see https://github.com/conbench/conbench/issues/862. This
    # fingerprint hashing approach has / will have similarities to Prometheus
    # Fingerprint/FastFingerprint. Let's think about likelihood for collisions,
    # and if there can be a fallout at all.
    ts_fingerprint = hashlib.md5(
        (benchmark_name + case_id + context_id + hardware_hash + repo_url).encode(
            "utf-8"
        )
    ).hexdigest()

    history = (
        current_session.query(
            BenchmarkResult,
            Hardware.hash.label("hardware_hash"),
            Commit.sha.label("commit_hash"),
            Commit.repository,
            Commit.message.label("commit_message"),
            Commit.timestamp.label("commit_timestamp"),
            Run.name.label("run_name"),
        )
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(Commit, Commit.id == Run.commit_id)
        .filter(
            BenchmarkResult.case_id == case_id,
            BenchmarkResult.context_id == context_id,
            BenchmarkResult.error.is_(None),
            # This `sha == Commit.fork_point_sha` cannot be satisfied for
            # results with an unknown commit context where commit parent/child
            # and branch information is not available. Consequence is to not
            # allow for history endpoint result for 'unknown context'.
            Commit.sha == Commit.fork_point_sha,  # on default branch
            Commit.repository == repo_url,
            Hardware.hash == hardware_hash,
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
                ts_fingerprint=ts_fingerprint,
                case_id=result.case_id,
                case_text_id=result.case.text_id,
                context_id=result.context_id,
                # Keep exposing the `mean` property like before. This was meant
                # to be the single value summary, guaranteed to have a value
                # set. So, actually read this from the new .svs property which
                # still is the mean as of today. Do not read this from
                # BenchmarkResult.mean, because this can be None.
                mean=result.svs,
                svs=result.svs,
                svs_type=result.svs_type,  # hard-code for now
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
                run_name=sample.run_name,
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
            data_point=_to_float_or_none(benchmark_result.mean),
            unit=benchmark_result.unit,
            dist_mean=_to_float_or_none(dist_mean),
            dist_stddev=_to_float_or_none(dist_stddev),
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
        current_session.query(commits)
        .order_by(commits.c.commit_order.desc())
        .limit(Config.DISTRIBUTION_COMMITS)
        .subquery()
    )

    # Find all historic results in the distribution to analyze
    history = (
        current_session.query(
            # we can use the `defer` method to not select all columns
            BenchmarkResult,
            Hardware.hash.label("hardware_hash"),
            s.sql.expression.literal(baseline_commit.repository).label("repository"),
            commits.c.ancestor_timestamp.label("commit_timestamp"),
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
            current_session.query(BenchmarkResult.case_id, BenchmarkResult.context_id)
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

    history_df, _ = execute_history_query_get_dataframe(history.statement)

    if len(history_df) == 0:
        return {}

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

    Note(JP): I once understood this but now I wonder: is this generating
    a dataframe for one meaningful timeseries (for one ts_fingerprint) or
    does this contain rows for various different timeseries (hence grouping
    would be necessary later on when further processing this)?

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
            # than result.run.commit.message below
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

        - BenchmarkResult: case_id
        - BenchmarkResult: context_id
        - BenchmarkResult: change_annotations
        - BenchmarkResult: svs (single value summary, currently mean)
        - BenchmarkResult: result_timestamp
        - Hardware: hash
        - Commit: repository
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
            .groupby(["case_id", "context_id", "hash", "repository", "segment_id"])
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
