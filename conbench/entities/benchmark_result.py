import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

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
from ..entities.commit import Commit, get_github_commit, repository_to_url
from ..entities.context import Context
from ..entities.distribution import update_distribution
from ..entities.hardware import Cluster, ClusterSchema, Machine, MachineSchema
from ..entities.info import Info
from ..entities.run import Run


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

    @staticmethod
    def create(data):
        tags = data["tags"]
        has_error = "error" in data

        if has_error:
            benchmark_result_data = {"error": data["error"]}
        else:
            benchmark_result_data = data["stats"]

        name = tags.pop("name")

        # create if not exists
        c = {"name": name, "tags": tags}
        case = Case.first(**c)
        if not case:
            case = Case.create(c)

        # create if not exists
        hardware_type, field_name = (
            (Machine, "machine_info")
            if "machine_info" in data
            else (Cluster, "cluster_info")
        )
        hardware = hardware_type.upsert(**data[field_name])

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

        sha, repository = None, None
        if "github" in data:
            sha = data["github"]["commit"]
            repository = repository_to_url(data["github"]["repository"])

        # create if not exists
        commit = Commit.first(sha=sha, repository=repository)
        if not commit:
            github = get_github_commit(repository, sha)
            if github:
                commit = Commit.create_github_context(sha, repository, github)
            elif sha or repository:
                commit = Commit.create_unknown_context(sha, repository)
            else:
                commit = Commit.create_no_context()

        # create if not exists
        run_id = data["run_id"]
        run_name = data.pop("run_name", None)
        run_reason = data.pop("run_reason", None)
        run = Run.first(id=run_id)
        if run:
            if has_error:
                run.has_errors = True
                run.save()
        else:
            run = Run.create(
                {
                    "id": run_id,
                    "name": run_name,
                    "reason": run_reason,
                    "commit_id": commit.id,
                    "hardware_id": hardware.id,
                    "has_errors": has_error,
                }
            )

        benchmark_result_data["run_id"] = data["run_id"]
        benchmark_result_data["batch_id"] = data["batch_id"]
        benchmark_result_data["timestamp"] = data["timestamp"]
        benchmark_result_data["case_id"] = case.id
        benchmark_result_data["info_id"] = info.id
        benchmark_result_data["context_id"] = context.id
        benchmark_result = BenchmarkResult(**benchmark_result_data)
        benchmark_result.save()

        if "error" in data:
            return benchmark_result

        update_distribution(benchmark_result, 100)

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


class GitHubCreate(marshmallow.Schema):
    commit = marshmallow.fields.String(required=True)
    repository = marshmallow.fields.String(required=True)


class _BenchmarkFacadeSchemaCreate(marshmallow.Schema):
    run_id = marshmallow.fields.String(required=True)
    run_name = marshmallow.fields.String(required=False)
    run_reason = marshmallow.fields.String(required=False)
    batch_id = marshmallow.fields.String(required=True)
    timestamp = marshmallow.fields.DateTime(required=True)
    machine_info = marshmallow.fields.Nested(MachineSchema().create, required=False)
    cluster_info = marshmallow.fields.Nested(ClusterSchema().create, required=False)
    stats = marshmallow.fields.Nested(BenchmarkResultSchema().create, required=False)
    error = marshmallow.fields.Dict(required=False)
    tags = marshmallow.fields.Dict(required=True)
    info = marshmallow.fields.Dict(required=True)
    context = marshmallow.fields.Dict(required=True)
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
