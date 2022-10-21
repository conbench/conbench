import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from ..db import Session
from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, Nullable
from ..entities.commit import (
    Commit,
    CommitSerializer,
    get_github_commit,
    repository_to_url,
)
from ..entities.hardware import (
    Cluster,
    ClusterSchema,
    Hardware,
    HardwareSerializer,
    Machine,
    MachineSchema,
)


class Run(Base, EntityMixin):
    __tablename__ = "run"
    id = NotNull(s.String(50), primary_key=True)
    name = Nullable(s.String(250))
    reason = Nullable(s.String(250))
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    finished_timestamp = Nullable(s.DateTime(timezone=False))
    info = Nullable(postgresql.JSONB)
    error_info = Nullable(postgresql.JSONB)
    error_type = Nullable(s.String(250))
    commit_id = NotNull(s.String(50), s.ForeignKey("commit.id"))
    commit = relationship("Commit", lazy="joined")
    has_errors = NotNull(s.Boolean, default=False)
    hardware_id = NotNull(s.String(50), s.ForeignKey("hardware.id"))
    hardware = relationship("Hardware", lazy="joined")

    @staticmethod
    def create(data):
        # create if not exists
        hardware_type, field_name = (
            (Machine, "machine_info")
            if "machine_info" in data
            else (Cluster, "cluster_info")
        )
        hardware = hardware_type.upsert(**data.pop(field_name))

        sha, repository = None, None

        if github_data := data.pop("github", None):
            sha = github_data["commit"]
            repository = repository_to_url(github_data["repository"])

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

        run = Run(**data, commit_id=commit.id, hardware_id=hardware.id)
        run.save()
        return run

    def get_baseline_run(self):
        from ..entities.benchmark_result import BenchmarkResult
        from ..entities.distribution import get_closest_parent

        result = (
            Session.query(
                BenchmarkResult.case_id,
                BenchmarkResult.context_id,
            )
            .filter(BenchmarkResult.run_id == self.id)
            .all()
        )
        run_items = [(row[0], row[1]) for row in result]
        hardware_entities = Hardware.all(hash=self.hardware.hash)
        hardware_ids = set([m.id for m in hardware_entities])

        parent = get_closest_parent(self)
        if not parent:
            return None

        # possible parent runs
        parent_runs = Run.search(
            filters=[
                Commit.sha == parent.sha,
                Hardware.id.in_(hardware_ids),
                Run.reason == "commit",
            ],
            joins=[Commit, Hardware],
            order_by=Run.timestamp.desc(),
        )

        # get run items for all possible parent runs
        parent_run_items = {run.id: [] for run in parent_runs}
        result = (
            Session.query(
                BenchmarkResult.run_id,
                BenchmarkResult.case_id,
                BenchmarkResult.context_id,
            )
            .filter(BenchmarkResult.run_id.in_(parent_run_items.keys()))
            .all()
        )
        for row in result:
            parent_run_items[row[0]].append((row[1], row[2]))

        # return last run with intersecting case and context pairs
        for parent_run in parent_runs:
            if set(run_items) & set(parent_run_items[parent_run.id]):
                return parent_run

        return None

    def get_baseline_id(self):
        run = self.get_baseline_run()
        return run.id if run else None


class _Serializer(EntitySerializer):
    def _dump(self, run):
        commit = CommitSerializer().one.dump(run.commit)
        hardware = HardwareSerializer().one.dump(run.hardware)
        commit.pop("links", None)
        hardware.pop("links", None)
        result = {
            "id": run.id,
            "name": run.name,
            "reason": run.reason,
            "timestamp": run.timestamp.isoformat(),
            "finished_timestamp": run.finished_timestamp.isoformat()
            if run.finished_timestamp
            else None,
            "info": run.info,
            "error_info": run.error_info,
            "error_type": run.error_type,
            "commit": commit,
            "hardware": hardware,
            "has_errors": run.has_errors,
            "links": {
                "list": f.url_for("api.runs", _external=True),
                "self": f.url_for("api.run", run_id=run.id, _external=True),
                "commit": f.url_for(
                    "api.commit", commit_id=commit["id"], _external=True
                ),
                "hardware": f.url_for(
                    "api.hardware", hardware_id=hardware["id"], _external=True
                ),
            },
        }
        if not self.many:
            baseline_id, baseline_url = run.get_baseline_id(), None
            if baseline_id:
                baseline_url = f.url_for("api.run", run_id=baseline_id, _external=True)
            result["links"]["baseline"] = baseline_url
        return result


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def commit_hardware_run_map():
    """
    Returns:
    {
        '246249 ARROW-15667: [R] Test development build with ARROW_BUILD_STATIC=OFF': {
            'date': '2022-03-03',
            'hardware': {
                'cluster A': [('2022-05-13 21:36 commit: 2462492389a8f2ca286c481852c84ba1f0d0eff9', 'runid1')],
                'machine A': [('2022-05-13 21:36 commit: 2462492389a8f2ca286c481852c84ba1f0d0eff9', 'runid2')]
            }
        }
    }
    """
    runs = Run.search(
        filters=[Commit.timestamp.isnot(None)],
        joins=[Commit, Hardware],
        order_by=Commit.timestamp.desc(),
    )

    results = {}

    for run in runs:
        commit = f"{run.commit.sha[:6]} {run.commit.message[:100]}{'...' if len(run.commit.message) > 100 else ''}"

        if commit not in results:
            commit_date = run.commit.timestamp.strftime("%Y-%m-%d")
            results[commit] = {"date": commit_date, "hardware": {}}

        if run.hardware.name not in results[commit]["hardware"]:
            results[commit]["hardware"][run.hardware.name] = []

        run_value = f"{run.timestamp.strftime('%Y-%m-%d %H:%M')} {run.name}"
        results[commit]["hardware"][run.hardware.name].append((run_value, run.id))

    return results


class GitHubCreate(marshmallow.Schema):
    commit = marshmallow.fields.String(required=True)
    repository = marshmallow.fields.String(required=True)


field_descriptions = {
    "finished_timestamp": "The datetime the run finished",
    "info": "Run's metadata",
    "error_info": "Metadata for run's error that prevented all or some benchmarks from running",
    "error_type": """Run's error type. Possible values: none, catastrophic, partial.
                    None = all attempted benchmarks are good.
                    Catastrophic =no benchmarks completed successfully.
                    Partial = some benchmarks completed, some failed""",
}


class _RunFacadeSchemaCreate(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    name = marshmallow.fields.String(required=False)
    reason = marshmallow.fields.String(required=False)
    finished_timestamp = marshmallow.fields.DateTime(
        required=False,
        metadata={"description": field_descriptions["finished_timestamp"]},
    )
    info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["info"]}
    )
    error_info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["error_info"]}
    )
    error_type = marshmallow.fields.String(
        required=False, metadata={"description": field_descriptions["error_type"]}
    )
    github = marshmallow.fields.Nested(GitHubCreate(), required=False)
    machine_info = marshmallow.fields.Nested(MachineSchema().create, required=False)
    cluster_info = marshmallow.fields.Nested(ClusterSchema().create, required=False)

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


class _RunFacadeSchemaUpdate(marshmallow.Schema):
    finished_timestamp = marshmallow.fields.DateTime(
        required=False,
        metadata={"description": field_descriptions["finished_timestamp"]},
    )
    info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["info"]}
    )
    error_info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["error_info"]}
    )
    error_type = marshmallow.fields.String(
        required=False, metadata={"description": field_descriptions["error_type"]}
    )


class RunFacadeSchema:
    create = _RunFacadeSchemaCreate()
    update = _RunFacadeSchemaUpdate()
