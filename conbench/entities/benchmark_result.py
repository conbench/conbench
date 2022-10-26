import flask as f
import marshmallow
import numpy as np
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from ..config import Config
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
from ..entities.distribution import update_distribution
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

    @staticmethod
    def create(data):
        tags = data["tags"]
        has_error = "error" in data

        if has_error:
            benchmark_result_data = {"error": data["error"]}
        # calculate any missing stats if data available
        elif data["stats"].get("data"):
            benchmark_result_data = data["stats"]
            dat = [float(x) for x in benchmark_result_data["data"]]
            q1, q3 = np.percentile(dat, [25, 75])

            calculated_result_data = {
                "data": dat,
                "times": data["stats"].get("times", []),
                "unit": data["stats"]["unit"],
                "time_unit": data["stats"].get("time_unit", "s"),
                "iterations": len(dat),
                "mean": np.mean(dat),
                "median": np.median(dat),
                "min": np.min(dat),
                "max": np.max(dat),
                "stdev": np.std(dat) if len(dat) > 2 else 0,
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1,
            }

            for field in calculated_result_data:
                # explicit `is None` because `stdev` is often 0
                if benchmark_result_data.get(field) is None:
                    benchmark_result_data[field] = calculated_result_data[field]
        else:
            benchmark_result_data = data["stats"]

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

        # create if not exists
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
        benchmark_result_data["timestamp"] = data["timestamp"]
        benchmark_result_data["validation"] = data.get("validation")
        benchmark_result_data["case_id"] = case.id
        benchmark_result_data["optional_benchmark_info"] = data.get(
            "optional_benchmark_info"
        )
        benchmark_result_data["info_id"] = info.id
        benchmark_result_data["context_id"] = context.id
        benchmark_result = BenchmarkResult(**benchmark_result_data)
        benchmark_result.save()

        if "error" in data:
            return benchmark_result

        update_distribution(benchmark_result, limit=Config.DISTRIBUTION_COMMITS)

        return benchmark_result


s.Index("benchmark_result_run_id_index", BenchmarkResult.run_id)
s.Index("benchmark_result_case_id_index", BenchmarkResult.case_id)
s.Index("benchmark_result_batch_id_index", BenchmarkResult.batch_id)
s.Index("benchmark_result_info_id_index", BenchmarkResult.info_id)
s.Index("benchmark_result_context_id_index", BenchmarkResult.context_id)


class BenchmarkResultCreate(marshmallow.Schema):
    data = marshmallow.fields.List(marshmallow.fields.Decimal, required=True)
    times = marshmallow.fields.List(marshmallow.fields.Decimal, required=True)
    unit = marshmallow.fields.String(required=True)
    time_unit = marshmallow.fields.String(required=True)
    iterations = marshmallow.fields.Integer(required=True)
    min = marshmallow.fields.Decimal(required=False)
    max = marshmallow.fields.Decimal(required=False)
    mean = marshmallow.fields.Decimal(required=False)
    median = marshmallow.fields.Decimal(required=False)
    stdev = marshmallow.fields.Decimal(required=False)
    q1 = marshmallow.fields.Decimal(required=False)
    q3 = marshmallow.fields.Decimal(required=False)
    iqr = marshmallow.fields.Decimal(required=False)


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
            "timestamp": benchmark_result.timestamp.isoformat(),
            "tags": tags,
            "optional_benchmark_info": benchmark_result.optional_benchmark_info,
            "validation": benchmark_result.validation,
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


class _BenchmarkFacadeSchemaCreate(marshmallow.Schema):
    run_id = marshmallow.fields.String(
        required=True,
        metadata={"description": "Unique identifier for a run of benchmarks."},
    )
    run_name = marshmallow.fields.String(
        required=False,
        metadata={
            "description": "Name for the run. When run in CI, this should be of the style '{run reason}: {commit sha}'."
        },
    )
    run_reason = marshmallow.fields.String(
        required=False,
        metadata={
            "description": "Reason for run (commit, pull request, manual, etc). This should be low cardinality. 'commit' is a special run_reason for commits on the default branch which are used for history"
        },
    )
    batch_id = marshmallow.fields.String(required=True)
    timestamp = marshmallow.fields.DateTime(
        required=True, metadata={"description": "Timestamp the benchmark ran"}
    )
    machine_info = marshmallow.fields.Nested(MachineSchema().create, required=False)
    cluster_info = marshmallow.fields.Nested(ClusterSchema().create, required=False)
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
    context = marshmallow.fields.Dict(
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

        if "stats" in data and "error" in data:
            raise marshmallow.ValidationError(
                "stats and error fields can not be used at the same time"
            )


class BenchmarkFacadeSchema:
    create = _BenchmarkFacadeSchemaCreate()
