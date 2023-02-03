from datetime import timezone

import flask as f
import marshmallow
import numpy as np
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

import conbench.util

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
from ..entities.case import Case
from ..entities.context import Context
from ..entities.hardware import ClusterSchema, MachineSchema
from ..entities.info import Info
from ..entities.run import GitHubCreate, Run


class BenchmarkResult(Base, EntityMixin):
    __tablename__ = "benchmark_result"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    case_id = NotNull(s.String(50), s.ForeignKey("case.id"))
    info_id = NotNull(s.String(50), s.ForeignKey("info.id"))
    context_id = NotNull(s.String(50), s.ForeignKey("context.id"))
    run_id = NotNull(s.Text, s.ForeignKey("run.id"))
    data = Nullable(postgresql.ARRAY(s.Numeric), default=[])
    times = Nullable(postgresql.ARRAY(s.Numeric), default=[])
    case = relationship("Case", lazy="joined")
    # optional info at the benchmark level (i.e. information that isn't a tag that should create a separate case, but information that's good to hold around like links to logs)
    optional_benchmark_info = Nullable(postgresql.JSONB)
    # this info should probably be called something like context-info it's details about the context that are optional | we believe won't impact performance
    info = relationship("Info", lazy="joined")
    context = relationship("Context", lazy="joined")
    run = relationship("Run", lazy="select")
    unit = Nullable(s.Text)
    time_unit = Nullable(s.Text)
    batch_id = Nullable(s.Text)
    # Do not store timezone information in the DB. Instead, follow timezone
    # convention: the application code must make sure that what we store is the
    # user-given time in UTC.
    timestamp = NotNull(s.DateTime(timezone=False))
    iterations = Nullable(s.Integer)
    min = Nullable(s.Numeric, check("min>=0"))
    max = Nullable(s.Numeric, check("max>=0"))
    mean = Nullable(s.Numeric, check("mean>=0"))
    median = Nullable(s.Numeric, check("median>=0"))
    stdev = Nullable(s.Numeric, check("stdev>=0"))
    q1 = Nullable(s.Numeric, check("q1>=0"))
    q3 = Nullable(s.Numeric, check("q3>=0"))
    iqr = Nullable(s.Numeric, check("iqr>=0"))
    error = Nullable(postgresql.JSONB)
    validation = Nullable(postgresql.JSONB)
    change_annotations = Nullable(postgresql.JSONB)

    @staticmethod
    def create(data):
        """Create BenchmarkResult and write to database."""
        tags = data["tags"]
        has_error = "error" in data
        has_stats = "stats" in data

        # defaults
        benchmark_result_data = {}
        complete_iterations = False

        if has_stats:
            benchmark_result_data = data["stats"]

            # calculate any missing stats if data available
            if data["stats"].get("data"):
                dat = [to_float(x) for x in benchmark_result_data["data"]]

                # defaults
                q1 = q3 = mean = median = min = max = stdev = iqr = None

                # calculate stats only if the data is complete
                complete_iterations = all([x is not None for x in dat])
                if complete_iterations:
                    q1, q3 = np.percentile(dat, [25, 75])
                    mean = np.mean(dat)
                    median = np.median(dat)
                    min = np.min(dat)
                    max = np.max(dat)
                    stdev = np.std(dat) if len(dat) > 2 else 0
                    iqr = q3 - q1

                calculated_result_data = {
                    "data": dat,
                    "times": data["stats"].get("times", []),
                    "unit": data["stats"]["unit"],
                    "time_unit": data["stats"].get("time_unit", "s"),
                    "iterations": len(dat),
                    "mean": mean,
                    "median": median,
                    "min": min,
                    "max": max,
                    "stdev": stdev,
                    "q1": q1,
                    "q3": q3,
                    "iqr": iqr,
                }

                for field in calculated_result_data:
                    # explicit `is None` because `stdev` is often 0
                    if benchmark_result_data.get(field) is None:
                        benchmark_result_data[field] = calculated_result_data[field]

        if has_error:
            benchmark_result_data["error"] = data["error"]

        # If there was no explicit error *and* the iterations aren't complete, we should add an error
        if (
            benchmark_result_data.get("error", None) is None
            and complete_iterations is False
        ):
            benchmark_result_data["error"] = {
                "status": "Partial result: not all iterations completed"
            }

        name = tags.pop("name")

        # create if not exists
        c = {"name": name, "tags": tags}
        case = Case.first(**c)
        if not case:
            case = Case.create(c)

        # create if not exists
        if "context" not in data:
            data["context"] = {}
        context = Context.first(tags=data["context"])
        if not context:
            context = Context.create({"tags": data["context"]})

        # create if not exists
        if "info" not in data:
            data["info"] = {}
        info = Info.first(tags=data["info"])
        if not info:
            info = Info.create({"tags": data["info"]})

        # Create a corresponding `run` entity in the database if it doesn't
        # exist yet. Use the user-given `id` (string) as primary key. If the
        # Run is already known in the database then only update the
        # `has_errors` property, if necessary. All other run-specific
        # properties provided as part of this BenchmarkCreate structure (like
        # `machine_info` and `run_name`) get silently ignored.
        run = Run.first(id=data["run_id"])
        if run:
            if has_error:
                run.has_errors = True
                run.save()
        else:
            hardware_info_field = (
                "machine_info" if "machine_info" in data else "cluster_info"
            )
            Run.create(
                {
                    "id": data["run_id"],
                    "name": data.pop("run_name", None),
                    "reason": data.pop("run_reason", None),
                    "github": data.pop("github", None),
                    hardware_info_field: data.pop(hardware_info_field),
                    "has_errors": has_error,
                }
            )

        benchmark_result_data["run_id"] = data["run_id"]
        benchmark_result_data["batch_id"] = data["batch_id"]

        # At this point `data["timestamp"]` is expected to be a tz-aware
        # datetime object in UTC.
        benchmark_result_data["timestamp"] = data["timestamp"]
        benchmark_result_data["validation"] = data.get("validation")
        benchmark_result_data["change_annotations"] = {
            key: value
            for key, value in data.get("change_annotations", {}).items()
            if value is not None
        }
        benchmark_result_data["case_id"] = case.id
        benchmark_result_data["optional_benchmark_info"] = data.get(
            "optional_benchmark_info"
        )
        benchmark_result_data["info_id"] = info.id
        benchmark_result_data["context_id"] = context.id
        benchmark_result = BenchmarkResult(**benchmark_result_data)
        benchmark_result.save()

        if "error" in data or not complete_iterations:
            return benchmark_result

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


s.Index("benchmark_result_run_id_index", BenchmarkResult.run_id)
s.Index("benchmark_result_case_id_index", BenchmarkResult.case_id)
s.Index("benchmark_result_batch_id_index", BenchmarkResult.batch_id)
s.Index("benchmark_result_info_id_index", BenchmarkResult.info_id)
s.Index("benchmark_result_context_id_index", BenchmarkResult.context_id)


class BenchmarkResultCreate(marshmallow.Schema):
    data = marshmallow.fields.List(
        marshmallow.fields.Decimal(allow_none=True),
        required=True,
        metadata={
            "description": "A list of benchmark results (e.g. durations, throughput). This will be used as the main + only metric for regression and improvement. The values should be ordered in the order the iterations were executed (the first element is the first iteration, the second element is the second iteration, etc.). If an iteration did not complete but others did and you want to send partial data, mark each iteration that didn't complete as `null`."
        },
    )
    times = marshmallow.fields.List(
        marshmallow.fields.Decimal(allow_none=True),
        required=True,
        metadata={
            "description": "A list of benchmark durations. If `data` is a duration measure, this should be a duplicate of that object. The values should be ordered in the order the iterations were executed (the first element is the first iteration, the second element is the second iteration, etc.). If an iteration did not complete but others did and you want to send partial data, mark each iteration that didn't complete as `null`."
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
            "description": "The minimum from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    max = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The maximum from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    mean = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The mean from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    median = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The median from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    stdev = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The standard deviation from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    q1 = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The first quartile from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    q3 = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The third quartile from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )
    iqr = marshmallow.fields.Decimal(
        required=False,
        metadata={
            "description": "The inter-quartile range from `data`, will be calculdated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing."
        },
    )


class BenchmarkResultSchema:
    create = BenchmarkResultCreate()


class _Serializer(EntitySerializer):
    def _dump(self, benchmark_result):
        z_score = float(benchmark_result.z_score) if benchmark_result.z_score else None
        case = benchmark_result.case
        tags = {"id": case.id, "name": case.name}
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
                "z_score": z_score,
                "z_regression": z_regression(benchmark_result.z_score),
                "z_improvement": z_improvement(benchmark_result.z_score),
            },
            "error": benchmark_result.error,
            "links": {
                "list": f.url_for("api.benchmarks", _external=True),
                "self": f.url_for(
                    "api.benchmark", benchmark_id=benchmark_result.id, _external=True
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


class _BenchmarkFacadeSchemaCreate(marshmallow.Schema):
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
    stats = marshmallow.fields.Nested(BenchmarkResultSchema().create, required=False)
    error = marshmallow.fields.Dict(
        required=False,
        metadata={
            "description": "Details about an error that occured while the benchamrk was running (free-form JSON)."
        },
    )
    tags = marshmallow.fields.Dict(
        required=True,
        metadata={
            "description": "Details that define the individual benchmark case that is being run (e.g. name, query type, data source, parameters). These are details about a benchmark that define different cases, for example: for a file reading benchmark, some tags might be: the data source being read, the compression that file is written in, the output format, etc."
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
    github = marshmallow.fields.Nested(GitHubCreate(), required=False)
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


class _BenchmarkFacadeSchemaUpdate(marshmallow.Schema):
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


class BenchmarkFacadeSchema:
    create = _BenchmarkFacadeSchemaCreate()
    update = _BenchmarkFacadeSchemaUpdate()
