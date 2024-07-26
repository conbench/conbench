import functools
import hashlib
import logging
import math
import statistics
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlparse

import flask as f
import marshmallow
import numpy as np
import sigfig
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, relationship

import conbench.units
import conbench.util
from conbench.config import Config
from conbench.dbsession import current_session
from conbench.numstr import numstr, numstr_dyn
from conbench.types import THistFingerprint
from conbench.units import KNOWN_UNIT_SYMBOLS_STR, TUnit, less_is_better

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    genprimkey,
    to_float,
)
from ..entities.case import Case
from ..entities.commit import (
    Commit,
    CommitSerializer,
    TypeCommitInfoGitHub,
    backfill_default_branch_commits,
    get_github_commit_metadata,
)
from ..entities.context import Context
from ..entities.hardware import (
    Cluster,
    ClusterSchema,
    Hardware,
    HardwareSerializer,
    Machine,
    MachineSchema,
)
from ..entities.info import Info

log = logging.getLogger(__name__)


class BenchmarkResultValidationError(Exception):
    pass


class BenchmarkResult(Base, EntityMixin):
    __tablename__ = "benchmark_result"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    case_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("case.id"))
    info_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("info.id"))
    context_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("context.id"))

    # An arbitrary string to group results by CI run. There are no assertions that this
    # string is non-empty.
    run_id: Mapped[str] = NotNull(s.Text)
    # Arbitrary tags for this CI run. Can be empty but not null. Has to be a flat
    # str/str mapping, and no key can be an empty string.
    run_tags: Mapped[Dict[str, str]] = NotNull(postgresql.JSONB)
    # A special tag that's often used in the UI, API, and DB queries.
    run_reason: Mapped[Optional[str]] = Nullable(s.Text)

    # The type annotation makes this a nullable many-to-one relationship.
    # https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#nullable-many-to-one
    # A nullable many-to-one relationship between Commit (one) and potentially
    # many results, but a result can also _not_ point to a commit.
    commit_id: Mapped[Optional[str]] = Nullable(s.ForeignKey("commit.id"))
    commit: Mapped[Optional[Commit]] = relationship("Commit", lazy="joined")

    # Non-empty URL to the repository without trailing slash.
    # Note(JP): maybe it is easier to think of this as just "repo_url" because
    # while it is not required that each result is associated with a particular
    # commit, but instead it is required to be associated with a (one!) code
    # repository as identified by its user-given repository URL.
    commit_repo_url: Mapped[str] = NotNull(s.Text)

    hardware_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("hardware.id"))
    hardware: Mapped[Hardware] = relationship("Hardware", lazy="joined")

    # The "fingerprint" (identifier) of this result's "history" (timeseries group). Two
    # results with the same history_fingerprint should be directly comparable, because
    # the relevant experimental variables have been controlled. Right now, those
    # variables are benchmark name & set of case parameter values, context, hardware,
    # and repository. This is a hash of those variables.
    history_fingerprint: Mapped[THistFingerprint] = NotNull(s.Text)

    # `data` holds the numeric values derived from N repetitions of the same
    # measurement (experiment). These can be empty lists. An item in the list
    # is of type float, which includes `math.nan` as valid value. Note(JP): I
    # think the type annotation `Optional[List[Optional[Decimal]]]` is now
    # finally correct, reflecting what we allow to be inserted into the DB. I
    # think we should really make it so that each element in self.data is of
    # type float.
    data: Mapped[Optional[List[Optional[Decimal]]]] = Nullable(
        postgresql.ARRAY(s.Numeric), default=[]
    )
    times: Mapped[Optional[List[Optional[Decimal]]]] = Nullable(
        postgresql.ARRAY(s.Numeric), default=[]
    )

    case: Mapped[Case] = relationship("Case", lazy="joined")
    # optional info at the benchmark level (i.e. information that isn't a tag that should create a separate case, but information that's good to hold around like links to logs)
    optional_benchmark_info: Mapped[Optional[dict]] = Nullable(postgresql.JSONB)
    # this info should probably be called something like context-info it's details about the context that are optional | we believe won't impact performance
    info: Mapped[Info] = relationship("Info", lazy="joined")
    context: Mapped[Context] = relationship("Context", lazy="joined")

    # Note(JP): `unit` can I think be null/none for errored benchmark results
    # (where no Stats structure was provided). When a stats structure was
    # provided then it is a string. Legacy DB might contain empty strings, but
    # now we have validation in the insert path that this is one of the allowed
    # unit symbol strings. Related:
    # https://github.com/conbench/conbench/issues/1335
    unit: Mapped[Optional[TUnit]] = Nullable(s.Text)

    time_unit: Mapped[Optional[str]] = Nullable(s.Text)

    batch_id: Mapped[Optional[str]] = Nullable(s.Text)

    # User-given 'benchmark start' time. Generally not a great criterion to
    # sort benchmark results by. Tracking insertion time would be better. Do
    # not store timezone information in this DB column. Instead, follow
    # timezone convention: the application code must make sure that what we
    # store is the user-given timestamp properly translated to UTC.
    timestamp: Mapped[datetime] = NotNull(s.DateTime(timezone=False))
    iterations: Mapped[Optional[int]] = Nullable(s.Integer)

    # Mean can only be None for errored BenchmarkResults. Is guaranteed to have
    # a numeric value for all non-errored BenchmarkResults, including those
    # that have just one data point (when the mean is not an exciting
    # statistic, but still a useful one).
    mean: Mapped[Optional[float]] = Nullable(s.Numeric, check("mean>=0"))

    # The remaining aggregates are only non-None when the BenchmarkResult has
    # at least N data points (see below).
    min: Mapped[Optional[float]] = Nullable(s.Numeric, check("min>=0"))
    max: Mapped[Optional[float]] = Nullable(s.Numeric, check("max>=0"))
    median: Mapped[Optional[float]] = Nullable(s.Numeric, check("median>=0"))
    stdev: Mapped[Optional[float]] = Nullable(s.Numeric, check("stdev>=0"))
    q1: Mapped[Optional[float]] = Nullable(s.Numeric, check("q1>=0"))
    q3: Mapped[Optional[float]] = Nullable(s.Numeric, check("q3>=0"))
    iqr: Mapped[Optional[float]] = Nullable(s.Numeric, check("iqr>=0"))
    error: Mapped[Optional[dict]] = Nullable(postgresql.JSONB)
    validation: Mapped[Optional[dict]] = Nullable(postgresql.JSONB)
    change_annotations: Mapped[Optional[dict]] = Nullable(postgresql.JSONB)

    @staticmethod
    # We should work towards having a precise type annotation for `data`. It's
    # the result of a (marshmallow) schema-validated JSON deserialization, and
    # therefore the type information _should_ be available already. However,  I
    # have not found a quick way to add a type annotation based on a
    # marshmallow schema. Maybe this would be a strong reason to move to using
    # pydantic -- I believe when defining a schema with pydantic, the
    # corresponding type information can be used for mypy automatically.
    # Also see https://stackoverflow.com/q/75662696/145400.
    def create(userres) -> "BenchmarkResult":
        """
        `userres`: user-given Benchmark Result object, after JSON
        deserialization.

        This is the result of marshmallow deserialization/validation against
        the `BenchmarkResultCreate` schema below. We should make use of typing
        information derived from the schema.

        Perform further validation on user-given data, and perform data
        mutation / augmentation.

        Attempt to write result to database.

        Create associated Case, Context, Info entities in DB if required.

        Raises BenchmarkResultValidationError, exc message is expected to be
        emitted to the HTTP client in a Bad Request response.
        """

        validate_and_augment_result_tags(userres)

        # The dict that is used for DB insertion later, populated below.
        result_data_for_db: Dict = {}

        if "stats" in userres:
            # First things first: use the complete user-given `stats` object
            # for potential DB insertion down below. In `error` state, do not
            # perform deeper validation of the user-given stats object (the
            # benchmark result is not used for any kind of analysis, which is
            # why it's probably ok to store the user-given 'stats' object w/o
            # deeper validation, maybe the data is helpful for debugging). Note
            # that what the user delivers under the `stats` key as a sub object
            # (in the result JSON object) is mapped directly on top-level
            # properties in the Python BenchmarkResult object. That is a bit of
            # an annoying asymmetry between DB object and JSON representation.
            result_data_for_db |= userres["stats"]  # PEP 584 update

        # User indicated error with variant A: user-given error object set.
        if "error" in userres:
            # We have business logic elsewhere that checks only for presence of
            # the `error` key (ignores its value, a value of `None` might
            # elsewhere be interpreted as error -- this did cost me 30 minutes
            # of debugging).
            result_data_for_db["error"] = userres["error"]

        # Check for a more subtle error condition based on the per-iteration
        # samples. Invariant: if "error" is not present then "stats" is present
        # as a key in this dictionary -- this is schema-enforced. he `stats`
        # object is guaranteed to have a `data` key.
        elif do_iteration_samples_look_like_error(userres["stats"]["data"]):
            # User indicated error with variant B: missing or incomplete data.
            # User unfortunately did not set `error` explicitly, but we err on
            # the side auf caution here and treat the result as 'errored'. This
            # is documented. Set generic error detail.
            result_data_for_db["error"] = {
                # Maybe tune this error message to be more generic.
                "status": "Partial result: not all iterations completed"
            }

        else:
            # process_samples_build_agg() must only be called if
            # do_iteration_samples_look_like_error() returned False. That's
            # the case here.
            result_data_from_stats = validate_and_aggregate_samples(userres["stats"])

            # Per-iteration samples looked good, and we did (potentially)
            # rebuild aggregates. Merge dict `result_stats_data_for_db` on top
            # of dict `benchmark_result_data`, overwriting upon conflict.
            result_data_for_db |= result_data_from_stats  # PEP 584 update

        # See https://github.com/conbench/conbench/issues/935,
        # At this point, assume that data["tags"] is a flat dictionary with
        # keys being non-empty strings, and values being non-empty strings.
        tags = userres["tags"]

        benchmark_name = tags.pop("name")

        # Create related DB entities if they do not exist yet.
        case = Case.get_or_create({"name": benchmark_name, "tags": tags})
        context = Context.get_or_create({"tags": userres["context"]})
        info = Info.get_or_create({"tags": userres.get("info", {})})
        if "machine_info" in userres:
            hardware = Machine.get_or_create(userres["machine_info"])
        else:
            hardware = Cluster.get_or_create(userres["cluster_info"])

        user_given_commit_info: TypeCommitInfoGitHub = userres["github"]
        repo_url = user_given_commit_info["repo_url"]
        commit = None
        if user_given_commit_info["commit_hash"] is not None:
            commit = commit_fetch_info_and_create_in_db_if_not_exists(
                user_given_commit_info
            )

        result_data_for_db["run_id"] = userres["run_id"]
        result_data_for_db["run_tags"] = userres.get("run_tags") or {}
        result_data_for_db["run_reason"] = userres.get("run_reason")

        # Legacy behavior: divert run_name into run_tags, if name is not already present
        # in run_tags.
        if "run_name" in userres and "name" not in result_data_for_db["run_tags"]:
            result_data_for_db["run_tags"]["name"] = userres["run_name"]

        result_data_for_db["batch_id"] = userres["batch_id"]

        # At this point `data["timestamp"]` is expected to be a tz-aware
        # datetime object in UTC.
        result_data_for_db["timestamp"] = userres["timestamp"]
        result_data_for_db["validation"] = userres.get("validation")
        result_data_for_db["change_annotations"] = {
            key: value
            for key, value in userres.get("change_annotations", {}).items()
            if value is not None
        }
        result_data_for_db["case_id"] = case.id
        result_data_for_db["optional_benchmark_info"] = userres.get(
            "optional_benchmark_info"
        )
        result_data_for_db["info_id"] = info.id
        result_data_for_db["context_id"] = context.id
        result_data_for_db["hardware_id"] = hardware.id
        result_data_for_db["commit_id"] = commit.id if commit else None
        result_data_for_db["commit_repo_url"] = repo_url
        result_data_for_db["history_fingerprint"] = generate_history_fingerprint(
            case_id=case.id,
            context_id=context.id,
            hardware_hash=hardware.hash,
            repo_url=repo_url,
        )
        benchmark_result = BenchmarkResult(**result_data_for_db)
        benchmark_result.save()

        return benchmark_result

    def update(self, data):
        old_change_annotations = self.change_annotations or {}

        # prefer newly-given change_annotations over old change_annotations
        new_change_annotations = {
            **old_change_annotations,
            **data.pop("change_annotations", {}),
        }
        # delete any new keys where value is None
        data["change_annotations"] = {
            key: value
            for key, value in new_change_annotations.items()
            if value is not None
        }

        super().update(data)

    def to_dict_for_json_api(benchmark_result, include_joins=True):
        # `self` is just convention :-P
        out_dict = {
            "id": benchmark_result.id,
            "run_id": benchmark_result.run_id,
            "run_tags": benchmark_result.run_tags,
            "run_reason": benchmark_result.run_reason,
            "commit_repo_url": benchmark_result.commit_repo_url,
            "batch_id": benchmark_result.batch_id,
            "history_fingerprint": benchmark_result.history_fingerprint,
            "timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.timestamp
            ),
            "optional_benchmark_info": benchmark_result.optional_benchmark_info,
            "validation": benchmark_result.validation,
            "change_annotations": benchmark_result.change_annotations or {},
            "stats": {
                "data": [to_float(x) for x in benchmark_result.data],
                "times": [to_float(x) for x in benchmark_result.times],
                "unit": benchmark_result.unit,
                "time_unit": benchmark_result.time_unit,
                "iterations": benchmark_result.iterations,
                "min": to_float(benchmark_result.min),
                "max": to_float(benchmark_result.max),
                "mean": to_float(benchmark_result.mean),
                "median": to_float(benchmark_result.median),
                "stdev": to_float(benchmark_result.stdev),
                "q1": to_float(benchmark_result.q1),
                "q3": to_float(benchmark_result.q3),
                "iqr": to_float(benchmark_result.iqr),
            },
            "error": benchmark_result.error,
        }

        if include_joins:
            case = benchmark_result.case
            # Note(JP): this is interesting, here we put the `name` and `id` keys
            # into tags. That is, the `tags` as returned may look different from
            # the tags as injected.
            tags = {"name": case.name}
            tags.update(case.tags)

            if benchmark_result.commit:
                commit_dict = CommitSerializer().many._dump(benchmark_result.commit)
                commit_dict.pop("links", None)
            else:
                commit_dict = None

            hardware_dict = HardwareSerializer().one.dump(benchmark_result.hardware)
            hardware_dict.pop("links", None)

            out_dict["tags"] = tags
            out_dict["commit"] = commit_dict
            out_dict["hardware"] = hardware_dict
            out_dict["links"] = {
                "list": f.url_for("api.benchmarks", _external=True),
                "self": f.url_for(
                    "api.benchmark",
                    benchmark_result_id=benchmark_result.id,
                    _external=True,
                ),
                "info": f.url_for(
                    "api.info", info_id=benchmark_result.info_id, _external=True
                ),
                "context": f.url_for(
                    "api.context",
                    context_id=benchmark_result.context_id,
                    _external=True,
                ),
                "run": f.url_for(
                    "api.run", run_id=benchmark_result.run_id, _external=True
                ),
            }

        return out_dict

    @functools.cached_property
    def is_failed(self):
        """
        Return True if this BenchmarkResult is considered to be 'failed' /
        erroneous.

        The criteria are conventions that we (hopefully) apply consistently
        across components.
        """
        if self.unit is None:
            return True

        if self.data is None:
            return True

        if self.error is not None:
            return True

        if do_iteration_samples_look_like_error(self.data):
            return True

        return False

    @property
    def svs(self) -> float:
        """
        Return single value summary or raise an Exception.
        """
        # This is here just for the shorter name.
        return self._single_value_summary()

    @property
    def svs_type(self) -> str:
        """
        Return single value summary type.
        """
        if Config.SVS_TYPE == "mean":
            return "mean"

        assert Config.SVS_TYPE == "best"

        if self.unit is None:
            return "n/a"
        elif less_is_better(self.unit):
            return "min"
        else:
            return "max"

    def _single_value_summary(self) -> float:
        """
        Return a single numeric value summarizing the collection of data points
        associated with this benchmark result.

        Return `math.nan` if this result is failed.

        Strategy:

        If Config.SVS_TYPE == "best", return the value of the "best" repetition. This is
        the minimum value if less_is_better, else the maximum value. Previously it was
        the mean value, but we saw that this was often skewed by outliers related to
        unavoidable benchmarking environment issues, which led to false positives during
        regression analysis. Much experience has taught us that when summarizing
        benchmark results over time, users care to omit those outliers and only look at
        the best-case scenarios.

        If Config.SVS_TYPE == "mean", return the mean of the data.

        Assumption: each non-errored benchmark result (self.is_failed is False)
        is guaranteed to have at least one data point.

        The value returned by this method is intended to be used in analysis
        and plotting routines.

        This method primarily serves the purpose of rather ignorantly mapping a
        collection of data points of unknown size (but at least 1) to a single
        value. This single-value summary may be the mean or min (or something
        else), and is not always statistically sound. But that is a type of
        problem that needs to be addressed with higher-level means (no pun
        intended).

        From a perspective of plotting, this here is the 'location' of the data
        point.

        Notes on terminology:

        - https://english.stackexchange.com/a/484587/70578
        - https://en.wikipedia.org/wiki/Summary_statistics

        Related issues:

        - https://github.com/conbench/conbench/issues/535
        - https://github.com/conbench/conbench/issues/640
        - https://github.com/conbench/conbench/issues/530
        """
        values = self.measurements

        if not values:
            return math.nan

        if Config.SVS_TYPE == "mean":
            if self.mean is None:
                # See https://github.com/conbench/conbench/issues/1169 -- Legacy
                # database might have mean being None _despite the benchmark not
                # being failed_. Because of a temporary logic error. Let's remove
                # this code path again for sanity. `values` (from
                # self.measurements) has only numbers.
                return statistics.mean(values)
            return float(self.mean)

        assert Config.SVS_TYPE == "best"
        # If there are values, a unit should be present.
        assert self.unit is not None

        if less_is_better(self.unit):
            return float(self.min) if self.min is not None else min(values)
        else:
            return float(self.max) if self.max is not None else max(values)

    @functools.cached_property
    def measurements(self) -> List[float]:
        """
        Return list of floats. Each item is guaranteed to not be NaN. The
        returned list may however be empty (for all failed results).

        For a non-failed result this list is guaranteed to have at least one
        item.

        This is an experiment for a hopefully valuable abstraction. I think we
        maybe want to make users of this class not use the `.data` property
        anymore.

        We also may want to instruct SQLAlchemy to return numbers as floats
        directly.
        """
        if self.is_failed:
            return []

        # The following two asserts explicitly document two assumptions that we
        # rely on to be valid after is_failed returned False. Also, these the
        # first assert statements is picked up by mypy for type inference.
        # Note that `assert all(d is not None for d in self.data)` did not help
        # mypy narrow down the type. See
        # https://github.com/python/mypy/issues/15180. To keep keep the
        # feedback tight I have now chosen the `if d is not None` plus length
        # constraint check, which should overall not have noticeable
        # performance impact.
        assert self.data is not None
        result = [float(d) for d in self.data if d is not None]
        assert len(result) == len(self.data)
        return result

    @functools.cached_property
    def ui_mean_and_uncertainty(self) -> str:
        return ui_mean_and_uncertainty(self.measurements, self.unit)

    @functools.cached_property
    def ui_rel_sem(self) -> Tuple[str, str]:
        return ui_rel_sem(self.measurements)

    @property
    def ui_non_null_sample_count(self) -> str:
        """
        The number of actual data points (with payload, a numeric value). If an
        individual iteration can report a `null`-like value, then this here is
        the number of samples.
        """
        if self.data is None:
            return "0"
        return str(len([x for x in self.data if x is not None]))

    @property
    def ui_time_started_at(self) -> str:
        """
        Return UI-friendly version of self.timestamp (user-given 'start time').
        """
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S") + " UTC"

    @property
    def ui_hardware_short(self) -> str:
        """
        Return hardware-representing short string, including user-given name
        and ID prefix.
        """
        hw = self.hardware
        if len(hw.name) > 15:
            return f"{hw.id[:4]}: " + hw.name[:15]

        return f"{hw.id[:4]}: " + hw.name

    def ui_commit_url_anchor(self) -> str:
        if self.commit is None:
            return '<a href="#">n/a</a>'
        return f'<a href="{self.commit.commit_url}">{self.commit.hash[:7]}</a>'

    @property
    def ui_commit_short_msg(self) -> str:
        if self.commit is None:
            return "n/a"
        return conbench.util.short_commit_msg(self.commit.message)

    @functools.cached_property
    def unitsymbol(self) -> Optional[conbench.units.TUnit]:
        """Return unit symbol or None if result indicates failure."""
        if self.is_failed:
            return None

        # Not None, and not an empty string.
        assert self.unit

        return conbench.units.legacy_convert(self.unit)


def ui_rel_sem(values: List[float]) -> Tuple[str, str]:
    """
    The first string in the tuple is a stringified float for sorting in a
    table. The second string in the tuple is for display in the table, with
    unit (percent).

    Associate "n/a" with a negative value so that DESC sorting by error is
    helpful.
    """
    if not values:
        # That is the case for 'failed'
        return (str(-1), "n/a (no data)")

    if all(v == 0 for v in values):
        return (str(-1), "n/a (bad data)")

    if len(values) < 3:
        return (str(-1), "n/a (< 3)")

    stdem = float(statistics.stdev(values)) / math.sqrt(len(values))

    # Express relative standard error in percent.
    # Seen with real-world data:
    # ZeroDivisionError: float division by zero
    rsep = 100 * (stdem / float(statistics.mean(values)))

    errstr = numstr(rsep, 2)
    return (errstr, f"{errstr} %")


def ui_mean_and_uncertainty(values: List[float], unit: Optional[str]) -> str:
    """
    Build human-readable text conveying the data acquired here.

    The returned string

        - includes a unit.
        - limits the number of significant digits.

    If this is a multi-sample data point then return notation like
    string like '3.1 ± 0.7'.

        mean_unc_str = sigfig.round(mean, uncertainty=stdem)

    It's difficult to write code like this because of
    https://github.com/conbench/conbench/issues/813
    and related discussions; I think we should really make it so that
    each element in self.data is of type float.

    """

    # Is this distinction helpful?
    # if is_failed:
    #    return "failed"

    if not values:
        return "no data"

    # Make sure that this is a non-empty string now (it can be passed as `None`
    # for an errored result, represented by `values` being empty in this case).
    assert unit

    if len(values) < 3:
        # Show each sample with fewish significant figures.
        return "; ".join(f"{numstr_dyn(v)} {unit}" for v in values)

    # Build sample standard deviation. Maybe we can also use the pre-built
    # value, but trust needs to be established first.
    stdev = statistics.stdev(values)
    mean = statistics.mean(values)

    # Calculate standard error of the mean for canonical scientific
    # notation of the result. Make float from Decimal, otherwise
    # TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'float'
    stdem = stdev / math.sqrt(len(values))

    # This generates a string like '3.1 ± 0.7'
    mean_uncertainty_str = sigfig.round(mean, uncertainty=stdem, warn=False)
    return f"({mean_uncertainty_str}) {unit}"


def validate_augment_unit_string(u: str) -> conbench.units.TUnit:
    """
    Raise BenchmarkResultValidationError for invalid unit string.

    Return augmented unit string, to be inserted into database.
    """
    if u == "b/s":
        # Rewrite short variant here for a legacy client, see
        # https://github.com/conbench/conbench/issues/1335
        # We might need/want to do a database migration where we rewrite
        # b/s to B/s.
        u = "B/s"

    if u not in conbench.units.KNOWN_UNITS:
        raise BenchmarkResultValidationError(
            f"invalid unit string `{u}`, pick one of: {conbench.units.KNOWN_UNIT_SYMBOLS_STR}"
        )

    return cast(conbench.units.TUnit, u)


def validate_and_aggregate_samples(stats_usergiven: Any):
    """
    Raises BenchmarkResultValidationError upon logical inconsistencies.

    `stats_usergiven` is deserialized JSON, validated against
    `BenchmarkResultStatsSchema(marshmallow.Schema)`.

    Only run this for the 'success' case, i.e. when the input is a list longer
    than zero, and each item is a number (not math.nan).

    Validate the user-given unit string also only in case of success, i.e.
    allow for 'bad units' to be submitted with 'errored' results.

    This returns a dictionary with key/value pairs meant for DB insertion,
    top-level for BenchmarkResult.
    """

    agg_keys = ("q1", "q3", "mean", "median", "min", "max", "stdev", "iqr")

    # Encode invariants. It seems that marshmallow.fields.Decimal allows for
    # both, str values and float values, and the test suite (at least today)
    # might inject string values.
    samples_input: List[Union[float, str]] = stats_usergiven["data"]

    # Proceed with float type.
    samples = [float(s) for s in samples_input]

    for sa in samples:
        assert not math.isnan(sa), sa

    # First copy the entire stats data structure (this includes times, data,
    # mean, min, ...). Later: selectively overwrite/augment.
    result_data_for_db = stats_usergiven.copy()

    result_data_for_db["unit"] = validate_augment_unit_string(
        result_data_for_db["unit"]
    )

    # And because numbers might have been provided as strings, make sure to
    # normalize to List[float] here.
    result_data_for_db["data"] = samples

    # Initialize all aggregate values explicitly to None (except for `mean`,
    # this has special treatment).
    for k in agg_keys:
        result_data_for_db[k] = None

    # The `mean` is the only aggregate that is OK to be built for at least one
    # data point (even if not that useful). That gives the guarantee that
    # BenchmarkResult.mean is populated for all non-errored BenchmarkResults.
    # See https://github.com/conbench/conbench/issues/1169
    result_data_for_db["mean"] = float(np.mean(samples))

    if len(samples) >= 3:
        # See https://github.com/conbench/conbench/issues/802 and
        # https://github.com/conbench/conbench/issues/1118
        percentiles: List[float] = list(np.percentile(samples, [25, 75]))
        q1, q3 = float(percentiles[0]), float(percentiles[1])

        aggregates: Dict[str, float] = {
            "q1": q1,
            "q3": q3,
            "median": float(np.median(samples)),
            "min": float(np.min(samples)),
            "max": float(np.max(samples)),
            # With ddof=1 this is Bessel's correction, has N-1 in the divisor.
            # This is the same behavior as
            # statistics.stdev() and the same behavior as
            # scipy.stats.tstd([1.0, 2, 3])
            "stdev": float(np.std(samples, ddof=1)),
            "iqr": q3 - q1,
        }

        # Now, overwrite with self-derived aggregates.
        for key, value in aggregates.items():
            result_data_for_db[key] = value

            # Log upon conflict. Let the automatically derived value win, to
            # achieve consistency between the provided samples and the
            # aggregates.
            if key in stats_usergiven:
                try:
                    if not floatcomp_with_leeway(float(stats_usergiven[key]), value):
                        log.warning(
                            "key %s, user-given val %s vs. calculated %s",
                            key,
                            stats_usergiven[key],
                            value,
                        )
                except Exception as exc:
                    log.warning(
                        "exception during floatcomp_with_leeway(): %s, stats_usergiven: %s",
                        exc,
                        stats_usergiven,
                    )

    # The next line explicitly encodes our updated thinking:
    # - `iterations` key is optional
    # - if provided, number is meant as 'micro benchmark iteration' count
    micro_bm_iterations: Optional[int] = stats_usergiven.get("iterations")

    if len(samples) == 1:
        if micro_bm_iterations == 1:
            # If user provides aggregates, then it's unclear what they mean.
            # That is, this set of user-given data is inconsistent. Ignore
            # parts of it. Tighter API specification / strictness would be
            # better when starting from scratch. But there are legacy clients
            # out there sending such data and we want to accept the 'ok' parts
            # about that ('be liberal in what you accept', well well).
            for k in agg_keys:
                val = stats_usergiven.get(k)
                if val is not None:
                    log.debug(
                        f"one data point from one iteration: stats property `{k}={val}` "
                        "is unexpected (do not store in DB)"
                    )

        if micro_bm_iterations and micro_bm_iterations > 1:
            # Note(JP): Do not yet handle this in a special way, but I think
            # that this here is precisely the one way to report the result of a
            # microbenchmark with cross-iteration stats: data: length 1 (the
            # duration of one _repetition_ involving potentially many
            # iterations, more than one). If mean, max, etc are now set then
            # these can be assumed to be derived from _within_ the
            # microbenchmark. For example, this could be useful for providing a
            # standard deviation derived from 100000 iterations (where it's
            # more or less obvious that we don't want to get 100000 raw samples
            # submitted). At the time of writing it is unclear if we have
            # clients / benchmark frameworks that can make use of that.
            ...

    if len(samples) == 2:
        # If user provides aggregates, then it's unclear what they mean.
        for k in agg_keys:
            val = stats_usergiven.get(k)
            if val is not None:
                log.warning(
                    f"with two data points the stats property `{k}={val}` "
                    "is unexpected (do not store in DB)"
                )

    return result_data_for_db


def floatcomp_with_leeway(v1: float, v2: float, sigfigs=2):
    """
    Confirm that two float values are roughly the same. Do that by reducing
    both to just S significant digits and then confirm that they don't deviate.
    This is as of the time of writing only used for generating warning log
    msgs.
    """
    v1s = numstr(v1, sigfigs=sigfigs)
    v2s = numstr(v2, sigfigs=sigfigs)
    return abs(float(v1s) - float(v2s)) < 10**-10


def do_iteration_samples_look_like_error(samples: List[Optional[Decimal]]) -> bool:
    """
    Inspect user-given numerical values for individual iteration results.
    Input is a list of either `None` or `Decimal` objects (currently enforced
    via marshmallow schema). Example: [Decimal('0.099094'), None,
    Decimal('0.036381')]
    Consider this multi-sample result as 'good' only when there is at least one
    numerical value and when _all_ values are numerical values.
    From https://github.com/conbench/conbench/issues/813: If stats.data
    contains at least one null value then the BenchmarkResult is considered
    failed. If no error information was provided by the user, then a dummy
    error message "not all iterations completed" is automatically set by
    Conbench upon DB insert.
    See https://github.com/conbench/conbench/pull/811#discussion_r1129144143
    """
    if len(samples) == 0:
        return True

    for sample in samples:
        if sample is None:
            return True

    return False


def validate_and_augment_result_tags(userres: Any):
    """
    Inspect and mutate userres['tags']. After that, all keys are non-empty
    strings, and all values are non-empty strings.

    See https://github.com/conbench/conbench/pull/948#discussion_r1149090197
    for background.

    Summary of current desired behavior: primitive value types are accepted
    (string, boolean, float, int; non-string values are converted to string
    before DB insertion). Other value types (array -> list, object -> dict)
    lead to request rejection.
    """

    tags = userres["tags"]

    # See: https://github.com/conbench/conbench/issues/935
    if "name" not in tags:
        raise BenchmarkResultValidationError(
            "`name` property must be present in `tags` "
            "(the name of the conceptual benchmark)"
        )

    # Iterate over a copy of key/value pairs.
    for key, value in list(tags.items()):
        # In JSON, a key is always of type string. We rely on this, codify
        # this invariant.
        assert isinstance(key, str)

        # An empty string is a valid JSON key. Do not allow this.
        if len(key) == 0:
            raise BenchmarkResultValidationError(
                "tags: zero-length string as key is not allowed"
            )

        # For now, be liberal in what we accept. Do not consider empty
        # string or None values for the case permutation (do not store
        # those in the DB, drop these key/value pairs). This is documented
        # in the API spec. Maybe in the future we want to reject such
        # requests with a Bad Request response.
        if value == "" or value is None:
            log.debug("drop tag key/value pair: `%s`, `%s`", key, value)
            # Remove current key/value pair, proceed with next key. This
            # mutates the dictionary `data["tags"]`; for keeping this a
            # sane operation the loop iterates over a copy of key/value
            # pairs.
            del tags[key]
            continue

        # Note(JP): this code path should go away after we adjust our
        # client tooling to not send numeric values anymore.
        if isinstance(value, (int, float, bool)):
            # I think we first want to adjust some client tooling before
            # enabling this log line:
            # log.warning("stringify case parameter value: `%s`, `%s`", key, value)
            # Replace value, proceed with next key.
            tags[key] = str(value)
            continue

        # This should be logically equivalent with the value being either
        # of type dict or of type list.
        if not isinstance(value, str):
            # Emit Bad Request response..
            raise BenchmarkResultValidationError(
                "tags: bad value type for key `{key}`, JSON object and array is not allowed`"
            )


def fetch_one_result_per_each_of_n_recent_runs(n: int = 250) -> List[BenchmarkResult]:
    """
    Uses a special "skip scan" query tailored for current implementation details
    (PostgreSQL 14, current DB schema). It is designed to quickly and efficiently obtain
    a handful of benchmark result rows from the results table, with each result having a
    unique run_id set, and results overall being sorted by time (most recent first). For
    more detail, see https://github.com/conbench/conbench/issues/1466.

    We used to scan all results, not limiting by timestamp. But the format of this query
    means it cannot take any shortcuts, and must scan the entire results table for all
    unique runs before sorting and limiting. This does not scale well. It's fine when
    the DB can use the shared buffer cache, but after a while this cache expires and
    this query can take >30s again reading all the data from disk. So we now filter to
    14 days ago. This takes advantage of the (run_id, timestamp) index, which is only a
    partial index: hence the '2023-11-19' filter. (This probably would be better handled
    with something like TimescaleDB.)

    Since this doesn't include joins, as of the time of writing we're still having to
    reach out to the database to get commit and hardware information: one query per
    result, I think. That SELECT query (one per result) will sometimes refer to the same
    commit since there can be multiple runs per commit.
    """
    query_text = f"""
        WITH RECURSIVE run_results AS (
            (
                SELECT *
                FROM benchmark_result
                WHERE timestamp > now() - INTERVAL '14 days'
                AND timestamp > '2023-11-19'
                ORDER BY run_id
                LIMIT 1
            )
            UNION ALL
            SELECT next_run.*
            FROM run_results
            CROSS JOIN LATERAL (
                SELECT *
                FROM benchmark_result
                WHERE run_id > run_results.run_id
                AND timestamp > now() - INTERVAL '14 days'
                AND timestamp > '2023-11-19'
                ORDER BY run_id
                LIMIT 1
            ) next_run
        )
        SELECT * FROM run_results
        ORDER BY timestamp desc
        LIMIT {n}
    """
    query = s.select(BenchmarkResult).from_statement(s.text(query_text))
    # Need to type hint this again because from_statement() overrides the type hints.
    bmrs: List[BenchmarkResult] = list(current_session.scalars(query, {"n": n}).all())
    return bmrs


def commit_fetch_info_and_create_in_db_if_not_exists(
    ghcommit: TypeCommitInfoGitHub,
) -> Commit:
    """
    Insert new Commit entity into database if required.

    If Commit not yet known in database: fetch data about commit (and related
    commits) from GitHub HTTP API if possible. Exceptions during this process
    are logged and otherwise swallowed.

    Return Commit.id (DB primary key) of existing Commit entity or of newly
    created one. Expect database collision upon insert (in this case the ID for
    the existing commit entity is returned).

    Has slightly ~unpredictable run duration as of interaction with GitHub HTTP
    API.
    """
    # Commit hash must be provided to use this function.
    assert ghcommit["commit_hash"]

    def _guts(cinfo: TypeCommitInfoGitHub) -> Tuple[Commit, bool]:
        """
        Return a Commit object or raise `sqlalchemy.exc.IntegrityError`.

        The boolean return value means "created", is `False` if the first
        query for the commit object succeeds, else `True.
        """
        # Commit hash must be provided to use this function.
        assert cinfo["commit_hash"]

        # Try to see if commit is already database. This is an optimization, to
        # not needlessly interact with the GitHub HTTP API in case the commit
        # is already in the database. first(): "Return the first result of this
        # Query or None if the result doesn’t contain any row.""
        dbcommit = Commit.first(sha=cinfo["commit_hash"], repository=cinfo["repo_url"])

        if dbcommit is not None:
            return dbcommit, False

        # Try to fetch metadata for commit via GitHub HTTP API. Fall back
        # gracefully if that does not work.
        gh_commit_metadata_dict = None
        try:
            # get_github_commit_metadata() may raise all those exceptions that can
            # happen during an HTTP request cycle. The repository might
            # for example not exist: Unexpected GitHub HTTP API response: <Response [404]
            gh_commit_metadata_dict = get_github_commit_metadata(cinfo)
        except Exception as exc:
            log.info(
                "treat as unknown context: error during get_github_commit_metadata(): %s",
                exc,
            )

        if gh_commit_metadata_dict:
            # We got data from GitHub. Insert into database.
            dbcommit = Commit.create_github_context(
                cinfo["commit_hash"], cinfo["repo_url"], gh_commit_metadata_dict
            )

            # The commit is known to GitHub. Fetch more data from GitHub.
            # Gracefully degrade if that does not work.
            try:
                backfill_default_branch_commits(cinfo["repo_url"], dbcommit)
            except Exception as exc:
                # Any error during this backfilling operation should not fail
                # the HTTP request processing (we're right now in the middle of
                # processing an HTTP request with new benchmark run data).
                log.info(
                    "Could not backfill default branch commits. Ignoring error "
                    "during backfill_default_branch_commits():  %s",
                    exc,
                )
                raise
            return dbcommit, True

        # Fetching metadata from GitHub failed. Store most important bits in
        # database.
        dbcommit = Commit.create_unknown_context(
            commit_hash=cinfo["commit_hash"], repo_url=cinfo["repo_url"]
        )
        return dbcommit, True

    created: bool = False
    t0 = time.monotonic()
    try:
        # `_guts()` is expected to raise IntegrityError when a concurrent racer
        # did insert the Commit object by now. This can happen, also see
        # https://github.com/conbench/conbench/issues/809
        commit, created = _guts(ghcommit)
    except s.exc.IntegrityError as exc:
        # Expected error example:
        #  sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation) \
        #    duplicate key value violates unique constraint "commit_index"
        log.info("Ignored IntegrityError while inserting Commit: %s", exc)
        # Look up the Commit entity again because this function must return the
        # commit ID (DB primary key).
        current_session.rollback()
        commit = Commit.first(
            sha=ghcommit["commit_hash"], repository=ghcommit["repo_url"]
        )

        # After IntegrityError we assume that Commit exists in DB. Encode
        # assumption, for easier debugging.
        assert commit is not None

    d_seconds = time.monotonic() - t0

    # Only log when the commit object was inserted (keep logs interesting,
    # reduce verbosity).
    if created:
        log.info(
            "commit_fetch_info_and_create_in_db_if_not_exists(%s) inserted, took %.3f s",
            ghcommit,
            d_seconds,
        )

    return commit


def generate_history_fingerprint(
    case_id: str, context_id: str, hardware_hash: str, repo_url: str
) -> str:
    """Generate a history_fingerprint from the relevant control variables."""
    # MD5 -- it's fine, it's fast, and I think collisions are practically impossible
    # (but that back-of-the-envelope calculation should at some point maybe be done, so
    # that at least current assumptions are documented: e.g., less than 10^6 individual
    # fingerprints or something like that).
    hash = hashlib.md5()

    # The unique index on Case means that its primary key is a unique identifier for the
    # specific benchmark name and case permutation (tags)
    hash.update(case_id.encode("utf-8"))

    # Similarly, Context has a unique index on its tags
    hash.update(context_id.encode("utf-8"))

    # The conventional field for checking whether two hardwares are compatible is
    # "hash". This might change in the future:
    # https://github.com/conbench/conbench/issues/1281
    hash.update(hardware_hash.encode("utf-8"))

    # Don't mix two repositories
    hash.update(repo_url.encode("utf-8"))

    return hash.hexdigest()


s.Index("benchmark_result_run_id_index", BenchmarkResult.run_id)
s.Index("benchmark_result_case_id_index", BenchmarkResult.case_id)

# Note(JP): we provde an API endpoint that allows for querying all benchmark
# results that have a certain batch name set. Therefore, this index is
# valuable.
s.Index("benchmark_result_batch_id_index", BenchmarkResult.batch_id)

s.Index("benchmark_result_info_id_index", BenchmarkResult.info_id)
s.Index("benchmark_result_context_id_index", BenchmarkResult.context_id)

# We order by benchmark_result.timestamp during many queries
s.Index("benchmark_result_timestamp_index", BenchmarkResult.timestamp)

# An important index. "Give me all comparable results" is a very common query.
s.Index(
    "benchmark_result_history_fingerprint_index", BenchmarkResult.history_fingerprint
)

# History queries look for specific commit_ids
s.Index("benchmark_result_commit_id_index", BenchmarkResult.commit_id)

# These indexes are important for how /api/benchmark-results/ accesses the DB for
# pagination.
s.Index(
    "benchmark_result_id_idx",
    BenchmarkResult.id,
    postgresql_where=(BenchmarkResult.timestamp >= "2023-06-03"),
)
s.Index(
    "benchmark_result_run_reason_id_idx",
    BenchmarkResult.run_reason,
    BenchmarkResult.id,
    postgresql_where=(BenchmarkResult.timestamp >= "2023-06-03"),
)

# This powers fetch_one_result_per_each_of_n_recent_runs().
s.Index(
    "benchmark_result_run_id_timestamp_idx",
    BenchmarkResult.run_id,
    BenchmarkResult.timestamp,
    postgresql_where=(BenchmarkResult.timestamp >= "2023-11-19"),
)


class _Serializer(EntitySerializer):
    def _dump(self, benchmark_result):
        return benchmark_result.to_dict_for_json_api()


class BenchmarkResultSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class BenchmarkResultStatsSchema(marshmallow.Schema):
    data = marshmallow.fields.List(
        marshmallow.fields.Decimal(allow_none=True),
        required=True,
        metadata={
            # Note(JP): we must specify: is it allowed to send an empty list?
            # Is it allowed to send a list with only `null` values? Should
            # there be the requirement that at least one non-null value must be
            # present?
            "description": conbench.util.dedent_rejoin(
                """
                A list of measurement results (e.g. duration, throughput).

                Each value in this list is meant to correspond to one
                repetition of ideally the exact same measurement.

                We recommend to repeat a measurement N times (3-6) for enabling
                systematic stability analysis.

                Values are expected to be ordered in the order the
                repetitions were executed (the first element
                corresponds to the first repetition, the second element is the
                second repetition, etc.).

                Values must be numeric or `null`: if one repetition failed but
                others did not you can mark the failed repetition as `null`.

                Note that you may populate both this field and the "error"
                field in the top level of the benchmark result payload.

                If any of the values in `data` is `null` or if the `error`
                field is set then Conbench will not include any of the reported
                data in automated analyses.
                """
            )
        },
    )
    times = marshmallow.fields.List(
        # https://github.com/conbench/conbench/issues/1399
        marshmallow.fields.Decimal(allow_none=True),
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Here, you can provide a list of benchmark durations. That can
                make sense if `data` is not a duration measure.

                Optional. If provided, must be a list of numbers. `null` is
                allowed to represent a failed repetition.

                The values should be ordered in the order the repetitions
                executed (the first element corresponds to the first
                repetition, the second element to the second repetition, etc).

                The `time_unit` field (see below) should be provided, too.

                Consider this as metadata. You can discover this field later
                via API and UI, however Conbench as of today does not do
                validation or analysis on the data.
                """
            )
        },
    )
    unit = marshmallow.fields.String(
        # I think in marshmallow terms this unfortunately means that empty
        # strings are/were allowed to be injected. TODO: be more strict.
        # Require users to provide a unit (non-zero length string)./
        # Update: validation for units is now done strictly for non-errored
        # results.
        required=True,
        metadata={
            "description": (
                "Unit of the numbers in `data`. Allowed values: "
                + KNOWN_UNIT_SYMBOLS_STR
            )
        },
    )
    time_unit = marshmallow.fields.String(
        # TODO/future: make this be intransparent metadata, and then later
        # maybe offer custom metrics from that metadata.
        # https://github.com/conbench/conbench/issues/1399
        required=False,
        metadata={
            "description": "The unit of the times object (e.g. seconds, nanoseconds)"
        },
    )
    iterations = marshmallow.fields.Integer(
        # TODO: make this not required, and clarify that these are
        # microbenchmark iterations, stored as metadata.
        # https://github.com/conbench/conbench/issues/1398
        required=False,
        metadata={
            "description": (
                "Here you can optionally store the number of microbenchmark "
                "iterations executed (per repetition). Treated as metadata. "
                "Do not store the number of repetitions here; this is reflected "
                "by the length of the `data` array."
            )
        },
    )
    min = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The minimum from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    max = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The maximum from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    mean = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The mean from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    median = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The median from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    stdev = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The standard deviation from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    q1 = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The first quartile from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    q3 = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The third quartile from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    iqr = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The inter-quartile range from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )


class SchemaGitHubCreate(marshmallow.Schema):
    """
    GitHub-flavored commit info object
    """

    @marshmallow.pre_load
    def change_empty_string_to_none(self, data, **kwargs):
        """For the specific situation of empty string being provided,
        treat this a None, _before_ schema validation.

        This for example alles the client to set pr_number to an empty string
        and this has the same meaning as setting it to `null` in the JSON doc.

        Otherwise, an empty string results in 'Not a valid integer' (for
        pr_number, at least).
        """
        for k in ("pr_number", "branch"):
            if data.get(k) == "":
                data[k] = None

        return data

    commit = marshmallow.fields.String(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                The commit hash of the benchmarked code.

                Must not be an empty string.

                Expected to be a known commit in the repository as specified by the
                `repository` URL property below.

                This property is optional. If not provided, it means that this benchmark
                result is not associated with a reproducible commit in the given
                repository.

                Not associating a benchmark result with a commit hash has special,
                limited purpose (pre-merge benchmarks, testing). It generally means that
                this benchmark result will not be considered for time series analysis
                along a commit tree.
                """
            )
        },
    )
    repository = marshmallow.fields.String(
        # Does this allow for empty strings or not?
        # Unclear, after reading marshmallow docs. Testes this. Yes, this
        # allows for empty string:
        # https://github.com/marshmallow-code/marshmallow/issues/76#issuecomment-1473348472
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                URL pointing to the benchmarked GitHub repository.

                Must be provided in the format https://github.com/org/repo.

                Trailing slashes are stripped off before database insertion.

                As of the time of writing, only URLs starting with
                "https://github.com" are allowed. Conbench interacts with the
                GitHub HTTP API in order to fetch information about the
                benchmarked repository. The Conbench user/operator is expected
                to ensure that Conbench is configured with a GitHub HTTP API
                authentication token that is privileged to read commit
                information for the repository specified here.

                Support for non-GitHub repositories (e.g. GitLab) or auxiliary
                repositories is interesting, but not yet well specified.
                """
            )
        },
    )
    pr_number = marshmallow.fields.Integer(
        required=False,
        allow_none=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                If set, this needs to be an integer or a stringified integer.

                This is the recommended way to indicate that this benchmark
                result has been obtained for a specific pull request branch.
                Conbench will use this pull request number to (try to) obtain
                branch information via the GitHub HTTP API.

                Set this to `null` or leave this out to indicate that this
                benchmark result has been obtained for the default branch.
                """
            )
        },
    )
    branch = marshmallow.fields.String(
        # All of these pass schema validation: empty string, non-empty-string,
        # null
        required=False,
        allow_none=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                This is an alternative way to indicate that this benchmark
                result has been obtained for a commit that is not on the
                default branch. Do not use this for GitHub pull requests (use
                the `pr_number` argument for that, see above).

                If set, this needs to be a string of the form `org:branch`.

                Warning: currently, if `branch` and `pr_number` are both
                provided, there is no error and `branch` takes precedence. Only
                use this when you know what you are doing.
                """
            )
        },
    )

    @marshmallow.validates_schema
    def validate_props(self, data, **kwargs):
        url = data["repository"]

        # Undocumented: transparently rewrite git@ to https:// URL -- let's
        # drop this in the future. Context:
        # https://github.com/conbench/conbench/pull/1134#discussion_r1170222541
        if url.startswith("git@github.com:"):
            url = url.replace("git@github.com:", "https://github.com/")
            data["repository"] = url

        if not url.startswith("https://github.com"):
            raise marshmallow.ValidationError(
                f"'repository' must be a URL, starting with 'https://github.com', got `{url}`"
            )

        try:
            urlparse(url)
        except ValueError as exc:
            raise marshmallow.ValidationError(
                f"'repository' failed URL validation: `{exc}`"
            )

        if "commit" in data and not len(data["commit"]):
            raise marshmallow.ValidationError("'commit' must be a non-empty string")

    @marshmallow.post_load
    def turn_into_predictable_return_type(self, data, **kwargs) -> TypeCommitInfoGitHub:
        """
        We really have to look into schema-inferred tight types, this here is a
        quick workaround for the rest of the code base to be able to work with
        `TypeCommitInfoGitHub`.
        """

        url: str = data["repository"].rstrip("/")
        # If we do not re-add this here as `None` then this property is _not_
        # part of the output dictionary if the user left this key out of
        # their JSON object
        commit_hash: Optional[str] = data.get("commit")
        pr_number: Optional[int] = data.get("pr_number")
        branch: Optional[str] = data.get("branch")

        result: TypeCommitInfoGitHub = {
            "repo_url": url,
            "commit_hash": commit_hash,
            "pr_number": pr_number,
            "branch": branch,
        }

        return result


# This is used in two places below.
CHANGE_ANNOTATIONS_DESC = """Post-analysis annotations about this BenchmarkResult that
give details about whether it represents a change, outlier, etc. in the overall
distribution of BenchmarkResults.

Currently-recognized keys that change Conbench behavior:

- `begins_distribution_change` (bool) - Is this result the first result of a sufficiently
"different" distribution than the result on the previous commit (for the same
hardware/case/context)? That is, when evaluating whether future results are regressions
or improvements, should we treat data from before this result as incomparable?
"""


class _BenchmarkResultCreateSchema(marshmallow.Schema):
    run_id = marshmallow.fields.String(
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Arbitrary identifier that you can use to group benchmark results.
                Typically used for a "run" of benchmarks (i.e. a single run of a CI
                pipeline) on a single commit and hardware. Required.

                The API does not ensure uniqueness (and, correspondingly, does not
                detect collisions). If your use case relies on this grouping construct
                then use a client-side ID generation scheme with negligible likelihood
                for collisions (e.g., UUID type 4 or similar).

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same `run_tags`, `run_reason`, hardware, and commit.
                There is no technical enforcement of this on the server side, so some
                behavior may not work as intended if this assumption is broken by the
                client.
                """
            )
        },
    )
    run_tags = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                An optional mapping of arbitrary keys and values that describe the CI
                run. These are used to group and filter runs in the UI and API. Do not
                include `run_reason` here; it should be provided below.

                For legacy reasons, if `run_name` is given when POSTing a benchmark
                result, it will be added to `run_tags` automatically under the `name`
                key. This will be its new permanent home.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same `run_tags`. There is no technical enforcement of
                this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    run_name = marshmallow.fields.String(
        required=False,
        metadata={
            "description": "A legacy attribute. Use `run_tags` instead. Optional."
        },
    )
    run_reason = marshmallow.fields.String(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Reason for the run (optional, does not need to be unique). A
                low-cardinality tag like `"commit"` or `"pull-request"`, used to group
                and filter runs, with special treatment in the UI and API.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same `run_reason`. There is no technical enforcement
                of this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    batch_id = marshmallow.fields.String(
        # this lacks specification and should probably not be required
        # see https://github.com/conbench/conbench/issues/880
        required=True
    )

    # `AwareDateTime` with `default_timezone` set to UTC: naive datetimes are
    # set this timezone.
    timestamp = marshmallow.fields.AwareDateTime(
        required=True,
        format="iso",
        default_timezone=timezone.utc,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                A datetime string indicating the time at which the benchmark
                was started. Expected to be in ISO 8601 notation.
                Timezone-aware notation recommended. Timezone-naive strings are
                interpreted in UTC. Fractions of seconds can be provided but
                are not returned by the API. Example value:
                2022-11-25T22:02:42Z. This timestamp defines the default
                sorting order when viewing a list of benchmarks via the UI or
                when enumerating benchmarks via the /api/benchmarks/ HTTP
                endpoint.
                """
            )
        },
    )
    machine_info = marshmallow.fields.Nested(
        MachineSchema().create,
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Precisely one of `machine_info` and `cluster_info` must be provided.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same hardware. There is no technical enforcement of
                this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    cluster_info = marshmallow.fields.Nested(
        ClusterSchema().create,
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Precisely one of `machine_info` and `cluster_info` must be provided.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same hardware. There is no technical enforcement of
                this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    stats = marshmallow.fields.Nested(BenchmarkResultStatsSchema(), required=False)
    error = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Details about an error that occurred while the benchmark was running
                (free-form JSON).

                You may populate both this field and the "data" field of the "stats"
                object. In that case, the "data" field measures the metric's values
                before the error occurred. Those values will not be compared to
                non-errored values in analyses and comparisons.
                """
            )
        },
    )
    tags = marshmallow.fields.Dict(
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                The set of key/value pairs that represents a specific benchmark
                case permutation (a specific set of parameters).

                Keys must be non-empty strings. Values should be non-empty
                strings.

                The special key "name" must be provided with a string value: it
                indicates the name of the conceptual benchmark that was
                performed for obtaining the result at hand. All case
                permutations of a conceptual benchmark by definition have this
                name in common.

                Example: a conceptual benchmark with name "foo-write-file"
                might have meaningful case permutations involving tag names
                such as `compression-method` (values: `gzip`, `lzma`, ...),
                `file-format` (values: `csv`, `hdf5`, ...), `dataset-name`
                (values: `foo`, `bar`, ...).

                For each conceptual benchmark, it is valid to have one or many
                case permutations (if you supply only "name", then there is
                necessarily a single mutation with the special property that it
                has no other tags set).

                We advise that each unique case (as defined by the complete set
                of key/value pairs) indeed corresponds to unique benchmarking
                behavior. That is, typically, all key/value pairs other than
                "name" directly correspond to input parameters to the same
                conceptual benchmark. Note however that Conbench benchmark
                result tags are not meant to store type information. Benchmark
                authors are advised to find a custom convention for mapping
                benchmark input parameters to tags.

                Currently, primitive value types (int, float, boolean) are
                accepted, but stored as strings. Keys with empty string values
                or null values are ignored. In the future, Conbench might
                disallow all non-string values.
                """
            )
        },
    )
    optional_benchmark_info = marshmallow.fields.Dict(
        required=False,
        metadata={
            # TODO: remove this.
            # https://github.com/conbench/conbench/issues/1424
            "description": "Deprecated. Use `info` instead."
        },
    )
    # Note, this mypy error is interesting: Incompatible types in assignment
    # (expression has type "marshmallow.fields.Dict", base class "Schema"
    # defined the type as "Dict[Any, Any]")
    context = marshmallow.fields.Dict(  # type: ignore[assignment]
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Required. Must be a JSON object (empty dictionary is allowed).

                Relevant benchmark context (other than hardware/platform
                details and benchmark case parameters).

                Conbench requires this object to remain constant when doing
                automated timeseries analysis (this breaks history).

                Use this to store for example compiler flags or a runtime
                version that you expect to have significant impact on
                measurement results.
                """
            )
        },
    )
    info = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Optional.

                Arbitrary metadata associated with this
                benchmark result.

                Ignored when assembling timeseries across results (differences
                do not break history).

                Must be a JSON object if provided. A flat string-string mapping
                is recommended (not yet enforced).

                This can be useful for example for storing URLs pointing to
                build artifacts. You can also use this to store environmental
                properties that you potentially would like to review later (a
                compiler version, or runtime version), and generally any kind
                of information that can later be useful for debugging
                unexpected measurements.
                """
            )
        },
    )
    validation = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": "Benchmark results validation metadata (e.g., errors, validation types)."
        },
    )
    github = marshmallow.fields.Nested(
        SchemaGitHubCreate(),
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                GitHub-flavored commit information. Required.

                Use this object to tell Conbench with which specific state of
                benchmarked code (repository identifier, possible commit hash) the
                BenchmarkResult is associated.
                """
            )
        },
    )
    change_annotations = marshmallow.fields.Dict(
        required=False, metadata={"description": CHANGE_ANNOTATIONS_DESC}
    )

    @marshmallow.validates_schema
    def validate_run_tags_schema(self, data, **kwargs):
        if "run_tags" not in data:
            return

        if not isinstance(data["run_tags"], dict):
            raise marshmallow.ValidationError("run_tags must be a map object")

        for key, value in data["run_tags"].items():
            if not isinstance(key, str) or len(key) == 0:
                raise marshmallow.ValidationError(
                    "run_tags keys must be non-empty strings"
                )
            if not isinstance(value, str):
                raise marshmallow.ValidationError("run_tags values must be strings")

    @marshmallow.validates_schema
    def validate_hardware_info_fields(self, data, **kwargs):
        if "machine_info" not in data and "cluster_info" not in data:
            raise marshmallow.ValidationError(
                "Either machine_info or cluster_info field is required"
            )

        if "machine_info" in data and "cluster_info" in data:
            raise marshmallow.ValidationError(
                "machine_info and cluster_info fields can not be used at the same time"
            )

    @marshmallow.validates_schema
    def validate_stats_or_error_field_is_present(self, data, **kwargs):
        if "stats" not in data and "error" not in data:
            raise marshmallow.ValidationError("Either stats or error field is required")

    @marshmallow.post_load
    def recalc_timestamp(self, data, **kwargs):
        curdt = data.get("timestamp")

        if curdt is None:
            return data

        data["timestamp"] = conbench.util.dt_shift_to_utc(curdt)
        return data


class _BenchmarkResultUpdateSchema(marshmallow.Schema):
    change_annotations = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": CHANGE_ANNOTATIONS_DESC
            + """

This endpoint will only update the user-specified keys, and leave the rest alone. To
delete an existing key, set the value to null.
"""
        },
    )


class BenchmarkResultFacadeSchema:
    create = _BenchmarkResultCreateSchema()
    update = _BenchmarkResultUpdateSchema()
