import logging
import math
import statistics
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import flask as f
import marshmallow
import numpy as np
import sigfig
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, relationship

import conbench.util
from conbench.db import Session

from ..entities._comparator import z_improvement, z_regression
from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    generate_uuid,
    to_float,
)
from ..entities.case import Case, get_case_or_create
from ..entities.commit import TypeCommitInfoGitHub
from ..entities.context import Context, get_context_or_create
from ..entities.hardware import ClusterSchema, MachineSchema
from ..entities.info import Info, get_info_or_create
from ..entities.run import Run, SchemaGitHubCreate

log = logging.getLogger(__name__)


class BenchmarkResultValidationError(Exception):
    pass


class BenchmarkResult(Base, EntityMixin):
    __tablename__ = "benchmark_result"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("case.id"))
    info_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("info.id"))
    context_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("context.id"))

    # Follow
    # https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#one-to-many
    # There is a one-to-many relationship between Run (one) and BenchmarkResult
    # (0, 1, many). Result is child. Run is parent. Child has column with
    # foreign key, pointing to parent.
    run_id: Mapped[str] = NotNull(s.Text, s.ForeignKey("run.id"))

    # Between Run (one) and Result (many) there is a one-to-many relationship
    # that we want to tell SQLAlchemy af ew things about via the following
    # `relationship()` call. Note that `lazy="select"` is a sane default here.
    # It means that another SELECT statement is issued upon attribute access
    # time. `select=immediate` would mean that items are to be loaded from the
    # DBas the parent is loaded, using a separate SELECT statement _per child_
    # (which did bite us, in particular for those Run entities associated with
    # O(1000) Result entities, i.e. hundreds of thousands of SELECT queries
    # were emitted for building the landing page. A joined query can always be
    # performed on demand.
    run: Mapped[Run] = relationship("Run", lazy="select", back_populates="results")

    # These can be empty lists. An item in the list is of type float, which
    # includes `math.nan` as valid value.
    data: Mapped[Optional[List[float]]] = Nullable(
        postgresql.ARRAY(s.Numeric), default=[]
    )
    times: Mapped[Optional[List[float]]] = Nullable(
        postgresql.ARRAY(s.Numeric), default=[]
    )

    case: Mapped[Case] = relationship("Case", lazy="joined")
    # optional info at the benchmark level (i.e. information that isn't a tag that should create a separate case, but information that's good to hold around like links to logs)
    optional_benchmark_info: Mapped[Optional[dict]] = Nullable(postgresql.JSONB)
    # this info should probably be called something like context-info it's details about the context that are optional | we believe won't impact performance
    info: Mapped[Info] = relationship("Info", lazy="joined")
    context: Mapped[Context] = relationship("Context", lazy="joined")

    # `unit` is required by schema and currently documented with "The unit of
    # the data object (e.g. seconds, B/s)". Where do we systematically keep
    # track of "less is better" or "more is better"?
    unit: Mapped[Optional[str]] = Nullable(s.Text)
    time_unit: Mapped[Optional[str]] = Nullable(s.Text)

    batch_id: Mapped[Optional[str]] = Nullable(s.Text)

    # User-given 'benchmark start' time. Generally not a great criterion to
    # sort benchmark results by. Tracking insertion time would be better. Do
    # not store timezone information in this DB column. Instead, follow
    # timezone convention: the application code must make sure that what we
    # store is the user-given timestamp properly translated to UTC.
    timestamp: Mapped[datetime] = NotNull(s.DateTime(timezone=False))
    iterations: Mapped[Optional[int]] = Nullable(s.Integer)
    min: Mapped[Optional[float]] = Nullable(s.Numeric, check("min>=0"))
    max: Mapped[Optional[float]] = Nullable(s.Numeric, check("max>=0"))
    mean: Mapped[Optional[float]] = Nullable(s.Numeric, check("mean>=0"))
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
    def create(userres):
        """
        `userres`: user-given Benchmark Result object, after JSON
        deserialization.

        This is the result of marshmallow deserialization/validation against
        the `BenchmarkResultCreate` schema below. We should make use of typing
        information derived from the schema.

        Perform further validation on user-given data, and perform data
        mutation / augmentation.

        Attempt to write result to database.

        Create associated Run, Case, Context, Info entities in DB if required.

        Raises BenchmarkResultValidationError, exc message is expected to be
        emitted to the HTTP client in a Bad Request response.
        """

        validate_and_augment_result_tags(userres)
        validate_run_result_consistency(userres)

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
        case = get_case_or_create({"name": benchmark_name, "tags": tags})
        context = get_context_or_create({"tags": userres["context"]})
        info = get_info_or_create({"tags": userres["info"]})

        # Create a corresponding `Run` entity in the database if it doesn't
        # exist yet. Use the user-given `id` (string) as primary key. If the
        # Run is already known in the database then only update the
        # `has_errors` property, if necessary. All other run-specific
        # properties provided as part of this BenchmarkResultCreate structure
        # (like `machine_info` and `run_name`) get silently ignored.
        run = Run.first(id=userres["run_id"])
        if run:
            if "error" in userres:
                run.has_errors = True
                run.save()
        else:
            hardware_info_field = (
                "machine_info" if "machine_info" in userres else "cluster_info"
            )
            Run.create(
                {
                    "id": userres["run_id"],
                    "name": userres.pop("run_name", None),
                    "reason": userres.pop("run_reason", None),
                    "github": userres.pop("github", None),
                    hardware_info_field: userres.pop(hardware_info_field),
                    "has_errors": "error" in userres,
                }
            )
            # The above's `create()` might fail (race condition), in which case
            # we can re-read, but then we also have to call
            # `validate_run_result_consistency(userres)` one more time (because
            # _we_ are not the ones who created the Run).

        result_data_for_db["run_id"] = userres["run_id"]
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

    def to_dict_for_json_api(benchmark_result):
        # `self` is just convention :-P
        #
        # Note(JP): Communicating the z-score as part of the benchmark result
        # object is a legacy approach. I think in the future we want to have a
        # property called `analyses` (or so, conceptually); and then this is
        # either empty, or shows details per-method. That could look like:
        #
        # analyses: { lookback-z-score: { z-score: 3.2, z-regression: true } }
        try:
            benchmark_result.z_score = float(benchmark_result.z_score)
        except (AttributeError, ValueError, TypeError):
            # Not all objects have this attribute set -> AttributeError.
            # Some objects might have a non-numeric value set? Not sure -> ValueError
            benchmark_result.z_score = None

        # Note(JP): having case/tags here is interesting; this requires a JOIN
        # query when fetching BenchmarkResult objects from the database.
        case = benchmark_result.case
        # Note(JP): this is interesting, here we put the `name` and `id` keys
        # into tags. That is, the `tags` as returned may look different from
        # the tags as injected.
        tags = {"name": case.name}
        tags.update(case.tags)
        return {
            "id": benchmark_result.id,
            "run_id": benchmark_result.run_id,
            "batch_id": benchmark_result.batch_id,
            "timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.timestamp
            ),
            "tags": tags,
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
                # Note(JP): it's interesting that this was added here into
                # `stats`, that's not a nice separation between input and
                # output.`
                "z_score": benchmark_result.z_score,
                "z_regression": z_regression(benchmark_result.z_score),
                "z_improvement": z_improvement(benchmark_result.z_score),
            },
            "error": benchmark_result.error,
            "links": {
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
            },
        }

    @property
    def ui_mean_and_uncertainty(self) -> str:
        """
        Build human-readable text conveying the data point acquired here.

        If this is a multi-sample data point then return notation like
        string like '3.1 ± 0.7'.

            mean_unc_str = sigfig.round(mean, uncertainty=stdem)

        It's difficult to write code like this because of
        https://github.com/conbench/conbench/issues/813
        and related discussions; I think we should really make it so that
        each element in self.data is of type float.

        """
        samples = self.data

        if samples is None:
            return "no data"

        # otherwise: `TypeError: can't convert type 'NoneType' to numerator/denominator`
        # in statistics.stdev(samples)
        samples = [s for s in samples if s is not None]

        if len(samples) < 3:
            # Show each sample with five significant figures.
            return "; ".join(str(sigfig.round(s, sigfigs=5)) for s in samples)

        # Build sample standard deviation. Maybe we can also use the pre-built
        # value, but trust needs to be established first.
        stdev = float(statistics.stdev(samples))
        mean = float(statistics.mean(samples))
        # Calculate standard error of the mean for canonical scientific
        # notation of the result. Make float from Decimal, otherwise
        # TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'float'
        stdem = stdev / math.sqrt(len(samples))

        # minstr = f"min: {sigfig.round(min, 3)} s"
        # This generates a string like '3.1 ± 0.7'
        mean_uncertainty_str = sigfig.round(mean, uncertainty=stdem)
        return f"({mean_uncertainty_str}) {self.unit}"  # err ~ {rsep_str} %"

    # maybe make this a cached property
    @property
    def ui_rel_sem(self) -> str:
        samples = self.data

        if samples is None:
            return "no data"

        # otherwise: `TypeError: can't convert type 'NoneType' to numerator/denominator`
        # in statistics.stdev(samples)
        samples = [s for s in samples if s is not None]

        if len(samples) < 3:
            return "n/a"

        stdem = float(statistics.stdev(samples)) / math.sqrt(len(samples))
        # Express relative standard error in percent.
        rsep = 100 * (stdem / float(statistics.mean(samples)))
        return f"{sigfig.round(rsep, sigfigs=2)} %"

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
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S") + " (UTC)"

    @property
    def ui_hardware_short(self) -> str:
        """
        Return hardware-representing short string, including user-given name
        and ID prefix.

        The indirection here through `self.run` is interesting, might trigger
        database interaction.
        """

        # try:
        #     # Note: is this jinja2 behavior? when this fails with
        #     # Attribute error like
        #     # 'BenchmarkResult' object has no attribute 'hardware'
        #     # then the template does not crash, but shows no value.
        #     print(type(self.hardware) + "f")
        # except Exception as exc:
        #     print("exc:", exc)
        #     raise exc

        hw = self.run.hardware
        if len(hw.name) > 15:
            return f"{hw.id[:4]}: " + hw.name[:15]

        return f"{hw.id[:4]}: " + hw.name


def validate_and_aggregate_samples(stats_usergiven: Any):
    """
    Raises BenchmarkResultValidationError upon logical inconsistencies.

    Only run this for the 'success' case, i.e. when the input is a list longer
    than zero, and each item is a number (not math.nan).

    This returns a dictionary with key/value pairs meant for DB insertion,
    top-level for BenchmarkResult.
    """

    agg_keys = ("q1", "q3", "mean", "median", "min", "max", "stdev", "iqr")

    # Encode invariants.
    samples = stats_usergiven["data"]
    assert len(samples) > 0
    for sa in samples:
        assert sa is not None
        assert sa != math.nan

    # Proceed with float type.
    samples = [float(s) for s in samples]

    # First copy the entire stats data structure (this includes times, data,
    # mean, min, ...). Later: selectively overwrite/augment.
    result_data_for_db = stats_usergiven.copy()

    # Initialize all aggregate values explicitly to None -- values set below
    # must be meaningful.
    for k in agg_keys:
        result_data_for_db[k] = None

    if len(samples) >= 2:
        # There is a special case where for one sample the iteration count
        # may be larger than one, see below.
        if stats_usergiven["iterations"] != len(samples):
            raise BenchmarkResultValidationError(
                f'iterations count ({ stats_usergiven["iterations"] }) does '
                f"not match sample count ({len(samples)})"
            )

    if len(samples) >= 3:
        # See https://github.com/conbench/conbench/issues/802 and
        # https://github.com/conbench/conbench/issues/1118
        q1, q3 = np.percentile(samples, [25, 75])

        aggregates = {
            "q1": q1,
            "q3": q3,
            "mean": np.mean(samples),
            "median": np.median(samples),
            "min": np.min(samples),
            "max": np.max(samples),
            # With ddof=1 this is Bessel's correction, has N-1 in the divisor.
            # This is the same behavior as
            # statistics.stdev() and the same behavior as
            # scipy.stats.tstd([1.0, 2, 3])
            "stdev": np.std(samples, ddof=1),
            "iqr": q3 - q1,
        }

        # Now, overwrite with self-derived aggregates:
        for key, value in aggregates.items():
            result_data_for_db[key] = sigfig.round(value, sigfigs=5)

            # Log upon conflict. Lett the automatically derived value win,
            # to achieve consistency between the provided samples and the
            # aggregates.
            if key in stats_usergiven:
                if not floatcomp(stats_usergiven[key], value):
                    log.warning(
                        "key %s, user-given val %s vs. calculated %s",
                        key,
                        stats_usergiven[key],
                        value,
                    )

    if len(samples) == 1:
        if stats_usergiven["iterations"] == 1:
            # If user provides aggregates, then it's unclear what they
            # mean.
            for k in agg_keys:
                if stats_usergiven.get(k) is not None:
                    raise BenchmarkResultValidationError(
                        f"one data point from one iteration: property `{k}` "
                        "is unexpected"
                    )

        if stats_usergiven["iterations"] > 1:
            # Note(JP): Do not yet handle this in a special way, but I think
            # that this here is precisely the one way to report the result of a
            # microbenchmark with cross-repetition stats: data: length 1 (the
            # duration of running many repetitions), and iterations: a number
            # larger than 1, while mean, max, are now set (then these can be
            # assumed to be derived from _within_ the microbenchmark. Note that
            # this is a very special condition). The mean time for a single
            # repetition now is sample/iterations.
            ...

    if len(samples) == 2:
        # If user provides aggregates, then it's unclear what they mean.
        for k in agg_keys:
            if stats_usergiven.get(k) is not None:
                raise BenchmarkResultValidationError(
                    f"with two provided data points, the property `{k}` "
                    "is unexpected"
                )

    return result_data_for_db


def floatcomp(v1, v2, sigfigs=5):
    v1s = sigfig.round(v1, sigfigs=sigfigs)
    v2s = sigfig.round(v2, sigfigs=sigfigs)
    return abs(float(v1s) - float(v2s)) < 10**-10


def do_iteration_samples_look_like_error(samples: list[Optional[Decimal]]) -> bool:
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
            log.warning("drop tag key/value pair: `%s`, `%s`", key, value)
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


def validate_run_result_consistency(userres: Any) -> None:
    """
    Read Run from database, based on userres["run_id"].

    Check for consistency between Result data and Run data.

    Raise BenchmarkResultValidationError in case there is a mismatch.

    This is a noop if the Run does not exist yet.

    Be sure to call this (latest) right before writing a BenchmarkResult object
    into the database, and after having created the Run object in the database.
    """
    run = Session.scalars(select(Run).where(Run.id == userres["run_id"])).first()

    if run is None:
        return

    # TODO: specification -- if userres.get("github") is None and if the Run
    # has associated commit information -- then consider this as a conflict or
    # not? what about branch name and PR number?

    # The property should not be called "github", this confuses me each
    # time I deal with that. This is the "github-flavored commit info".

    gh_commit_info: Optional[TypeCommitInfoGitHub] = userres.get("github")
    if gh_commit_info is not None:
        chrun = run.commit.hash if run.commit else None
        chresult = gh_commit_info["commit_hash"]
        if chrun != chresult:
            raise BenchmarkResultValidationError(
                f"Result refers to commit hash '{chresult}', but Run '{run.id}' "
                f"refers to commit hash '{chrun}'"
            )

        # Cannot do this yet, this is too complicated as of None/empty
        # string confusion repo_url_run = run.commit.repo_url
        # repo_url_result = userres["github"]["repository"] if
        # repo_url_run != repo_url_result: raise
        #     BenchmarkResultValidationError( f"Result refers to
        #         repository URL '{repo_url_result}', but Run
        #         '{run.id}' " f"refers to repository URL
        #     '{repo_url_run}'" )


s.Index("benchmark_result_run_id_index", BenchmarkResult.run_id)
s.Index("benchmark_result_case_id_index", BenchmarkResult.case_id)

# Note(JP): we provde an API endpoint that allows for querying all benchmark
# results that have a certain batch name set. Therefore, this index is
# valuable.
s.Index("benchmark_result_batch_id_index", BenchmarkResult.batch_id)

s.Index("benchmark_result_info_id_index", BenchmarkResult.info_id)
s.Index("benchmark_result_context_id_index", BenchmarkResult.context_id)

# We order by benchmark_result.timestamp in /api/benchmarks/ -- that wants
# and index!
s.Index("benchmark_result_timestamp_index", BenchmarkResult.timestamp)


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
                A list of benchmark results (e.g. durations, throughput). This
                will be used as the main + only metric for regression and
                improvement. The values should be ordered in the order the
                iterations were executed (the first element is the first
                iteration, the second element is the second iteration, etc.).
                If an iteration did not complete but others did and you want to
                send partial data, mark each iteration that didn't complete as
                `null`.

                You may populate both this field and the "error" field in the top level
                of the benchmark result payload. In that case, this field measures
                the metric's values before the error occurred. These values will not be
                compared to non-errored values in analyses and comparisons.
                """
            )
        },
    )
    times = marshmallow.fields.List(
        marshmallow.fields.Decimal(allow_none=True),
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                A list of benchmark durations. If `data` is a duration measure,
                this should be a duplicate of that object. The values should be
                ordered in the order the iterations were executed (the first
                element is the first iteration, the second element is the
                second iteration, etc.). If an iteration did not complete but
                others did and you want to send partial data, mark each
                iteration that didn't complete as `null`.

                You may populate both this field and the "error" field in the top level
                of the benchmark result payload. In that case, this field measures
                how long the benchmark took to run before the error occurred. These
                values will not be compared to non-errored values in analyses and
                comparisons.
                """
            )
        },
    )
    unit = marshmallow.fields.String(
        required=True,
        metadata={"description": "The unit of the data object (e.g. seconds, B/s)"},
    )
    time_unit = marshmallow.fields.String(
        required=True,
        metadata={
            "description": "The unit of the times object (e.g. seconds, nanoseconds)"
        },
    )
    iterations = marshmallow.fields.Integer(
        required=True,
        metadata={
            "description": "Number of iterations that were executed (should be the length of `data` and `times`)"
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


class _Serializer(EntitySerializer):
    def _dump(self, benchmark_result):
        return benchmark_result.to_dict_for_json_api()


class BenchmarkResultSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


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
                Identifier for a Run (required). This can be the ID of a known
                Run (as returned by /api/runs) or a new ID in which case a new
                Run entity is created in the database.
                """
            )
        },
    )
    run_name = marshmallow.fields.String(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Name for the Run (optional, does not need to be unique). Can be
                useful for implementing a custom naming convention. For
                organizing your benchmarks, and for enhanced search &
                discoverability. Ignored when Run was previously created.
                """
            )
        },
    )
    run_reason = marshmallow.fields.String(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Reason for the Run (optional, does not need to be unique).
                Ignored when Run was previously created.
                """
            )
        },
    )
    batch_id = marshmallow.fields.String(required=True)

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
                Precisely one of `machine_info` and `cluster_info` must be
                provided. The data is however ignored when the Run (referred to
                by `run_id`) was previously created.
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
                Precisely one of `machine_info` and `cluster_info` must be
                provided. The data is however ignored when the Run (referred to
                by `run_id`) was previously created.
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
            "description": "Optional information about Benchmark results (e.g., telemetry links, logs links). These are unique to each benchmark that is run, but are information that aren't reasonably expected to impact benchmark performance. Helpful for adding debugging or additional links and context for a benchmark (free-form JSON)"
        },
    )
    # Note, this mypy error is interesting: Incompatible types in assignment
    # (expression has type "marshmallow.fields.Dict", base class "Schema"
    # defined the type as "Dict[Any, Any]")
    context = marshmallow.fields.Dict(  # type: ignore[assignment]
        required=True,
        metadata={
            "description": "Information about the context the benchmark was run in (e.g. compiler flags, benchmark langauge) that are reasonably expected to have an impact on benchmark performance. This information is expected to be the same across a number of benchmarks. (free-form JSON)"
        },
    )
    info = marshmallow.fields.Dict(
        required=True,
        metadata={
            "description": "Additional information about the context the benchmark was run in that is not expected to have an impact on benchmark performance (e.g. benchmark language version, compiler version). This information is expected to be the same across a number of benchmarks. (free-form JSON)"
        },
    )
    validation = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": "Benchmark results validation metadata (e.g., errors, validation types)."
        },
    )
    github = marshmallow.fields.Nested(SchemaGitHubCreate(), required=False)
    change_annotations = marshmallow.fields.Dict(
        required=False, metadata={"description": CHANGE_ANNOTATIONS_DESC}
    )

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
