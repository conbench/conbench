import decimal

import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.orm import relationship

from ..entities._comparator import z_improvement, z_regression
from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    generate_uuid,
)
from ..entities.case import Case
from ..entities.commit import Commit, get_github_commit, repository_to_url
from ..entities.context import Context
from ..entities.data import Data
from ..entities.distribution import update_distribution
from ..entities.machine import Machine, MachineSchema
from ..entities.run import Run
from ..entities.time import Time


class Summary(Base, EntityMixin):
    __tablename__ = "summary"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    case_id = NotNull(s.String(50), s.ForeignKey("case.id"))
    context_id = NotNull(s.String(50), s.ForeignKey("context.id"))
    run_id = NotNull(s.Text, s.ForeignKey("run.id"))
    case = relationship("Case", lazy="joined")
    context = relationship("Context", lazy="joined")
    run = relationship("Run", lazy="select")
    data = relationship(
        "Data",
        lazy="joined",
        cascade="all, delete",
        passive_deletes=True,
    )
    times = relationship(
        "Time",
        lazy="joined",
        cascade="all, delete",
        passive_deletes=True,
    )
    unit = NotNull(s.Text)
    time_unit = NotNull(s.Text)
    batch_id = NotNull(s.Text)
    timestamp = NotNull(s.DateTime(timezone=False))
    iterations = NotNull(s.Integer, check("iterations>=1"))
    min = Nullable(s.Numeric, check("min>=0"))
    max = Nullable(s.Numeric, check("max>=0"))
    mean = Nullable(s.Numeric, check("mean>=0"))
    median = Nullable(s.Numeric, check("median>=0"))
    stdev = Nullable(s.Numeric, check("stdev>=0"))
    q1 = Nullable(s.Numeric, check("q1>=0"))
    q3 = Nullable(s.Numeric, check("q3>=0"))
    iqr = Nullable(s.Numeric, check("iqr>=0"))

    @staticmethod
    def create(data):
        tags = data["tags"]
        stats = data["stats"]
        name = tags.pop("name")
        values = stats.pop("data")
        times = stats.pop("times")

        # create if not exists
        c = {"name": name, "tags": tags}
        case = Case.first(**c)
        if not case:
            case = Case.create(c)

        # create if not exists
        machine = Machine.first(**data["machine_info"])
        if not machine:
            machine = Machine.create(data["machine_info"])

        # create if not exists
        context = Context.first(tags=data["context"])
        if not context:
            context = Context.create({"tags": data["context"]})

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
        run = Run.first(id=run_id)
        if not run:
            run = Run.create(
                {
                    "id": run_id,
                    "name": run_name,
                    "commit_id": commit.id,
                    "machine_id": machine.id,
                }
            )

        stats["run_id"] = data["run_id"]
        stats["batch_id"] = data["batch_id"]
        stats["timestamp"] = data["timestamp"]
        stats["case_id"] = case.id
        stats["context_id"] = context.id
        summary = Summary(**stats)
        summary.save()

        values = [decimal.Decimal(x) for x in values]
        bulk = []
        for i, x in enumerate(values):
            bulk.append(Data(result=x, summary_id=summary.id, iteration=i + 1))
        Data.bulk_save_objects(bulk)

        times = [decimal.Decimal(x) for x in times]
        bulk = []
        for i, x in enumerate(times):
            bulk.append(Time(result=x, summary_id=summary.id, iteration=i + 1))
        Time.bulk_save_objects(bulk)

        update_distribution(summary, 100)

        return summary


s.Index("summary_run_id_index", Summary.run_id)
s.Index("summary_case_id_index", Summary.case_id)
s.Index("summary_batch_id_index", Summary.batch_id)


class SummaryCreate(marshmallow.Schema):
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


class SummarySchema:
    create = SummaryCreate()


class _Serializer(EntitySerializer):
    decimal_fmt = "{:.6f}"

    def _dump(self, summary):
        by_iteration_data = sorted([(x.iteration, x.result) for x in summary.data])
        data = [result for _, result in by_iteration_data]
        by_iteration_times = sorted([(x.iteration, x.result) for x in summary.times])
        times = [result for _, result in by_iteration_times]
        z_score = self.decimal_fmt.format(summary.z_score) if summary.z_score else None
        case = summary.case
        tags = {"id": case.id, "name": case.name}
        tags.update(case.tags)
        return {
            "id": summary.id,
            "run_id": summary.run_id,
            "batch_id": summary.batch_id,
            "timestamp": summary.timestamp.isoformat(),
            "tags": tags,
            "stats": {
                "data": [self.decimal_fmt.format(x) for x in data],
                "times": [self.decimal_fmt.format(x) for x in times],
                "unit": summary.unit,
                "time_unit": summary.time_unit,
                "iterations": summary.iterations,
                "min": self.decimal_fmt.format(summary.min),
                "max": self.decimal_fmt.format(summary.max),
                "mean": self.decimal_fmt.format(summary.mean),
                "median": self.decimal_fmt.format(summary.median),
                "stdev": self.decimal_fmt.format(summary.stdev),
                "q1": self.decimal_fmt.format(summary.q1),
                "q3": self.decimal_fmt.format(summary.q3),
                "iqr": self.decimal_fmt.format(summary.iqr),
                "z_score": z_score,
                "z_regression": z_regression(summary.z_score),
                "z_improvement": z_improvement(summary.z_score),
            },
            "links": {
                "list": f.url_for("api.benchmarks", _external=True),
                "self": f.url_for(
                    "api.benchmark", benchmark_id=summary.id, _external=True
                ),
                "context": f.url_for(
                    "api.context", context_id=summary.context_id, _external=True
                ),
                "run": f.url_for("api.run", run_id=summary.run_id, _external=True),
            },
        }


class SummarySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class GitHubCreate(marshmallow.Schema):
    commit = marshmallow.fields.String(required=True)
    repository = marshmallow.fields.String(required=True)


class _BenchmarkFacadeSchemaCreate(marshmallow.Schema):
    run_id = marshmallow.fields.String(required=True)
    run_name = marshmallow.fields.String(required=False)
    batch_id = marshmallow.fields.String(required=True)
    timestamp = marshmallow.fields.DateTime(required=True)
    machine_info = marshmallow.fields.Nested(MachineSchema().create, required=True)
    stats = marshmallow.fields.Nested(SummarySchema().create, required=True)
    tags = marshmallow.fields.Dict(required=True)
    context = marshmallow.fields.Dict(required=True)
    github = marshmallow.fields.Nested(GitHubCreate(), required=False)


class BenchmarkFacadeSchema:
    create = _BenchmarkFacadeSchemaCreate()
