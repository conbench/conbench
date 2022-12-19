import logging
from typing import Optional

import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from ..db import Session
from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, Nullable
from ..entities.commit import (
    CantFindAncestorCommitsError,
    Commit,
    CommitSerializer,
    backfill_default_branch_commits,
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

log = logging.getLogger(__name__)


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

        repository, pr_number, branch, sha = None, None, None, None

        if github_data := data.pop("github", None):
            repository = repository_to_url(github_data["repository"])
            pr_number = github_data.get("pr_number")
            branch = github_data.get("branch")
            sha = github_data["commit"]

        # create if not exists
        commit = Commit.first(sha=sha, repository=repository)

        if not commit:

            # Try to fetch data via GitHub HTTP API
            gh_commit_dict = None
            try:
                # get_github_commit() may raise all those exceptions that can
                # happen during an HTTP request cycle.
                gh_commit_dict = get_github_commit(
                    repository=repository, pr_number=pr_number, branch=branch, sha=sha
                )
            except Exception as exc:
                log.info(
                    "treat as unknown commit: error during get_github_commit(): %s", exc
                )

            if gh_commit_dict:
                commit = Commit.create_github_context(sha, repository, gh_commit_dict)
                try:
                    backfill_default_branch_commits(repository, commit)
                except Exception as e:
                    # no matter what happened during backfilling, we want to return a
                    # successful status code because the commit was created
                    log.info(
                        "Could not backfill default branch commits. Error "
                        "during backfill_default_branch_commits():  %s",
                        e,
                    )

            elif sha or repository:
                commit = Commit.create_unknown_context(sha, repository)
            else:
                commit = Commit.create_no_context()

        run = Run(**data, commit_id=commit.id, hardware_id=hardware.id)
        run.save()
        return run

    def get_baseline_run(self) -> Optional["Run"]:
        """Return the closest ancestor of this Run that:

        - is in this Run's commit ancestry
        - shares this Run's reason (but see note)
        - has *any* BenchmarkResults that share the hardware/case/context of *any* of
            this Run's BenchmarkResults

        Note: if there are no matches for those criteria, we search for ANY run_reason
        on the default branch. This helps runs on the first commits of pull requests.

        Returns None if there are no matches.
        Returns a random Run if there are multiple matches.
        """
        from ..entities.benchmark_result import BenchmarkResult

        commit: Commit = self.commit
        try:
            ancestor_commits = commit.commit_ancestry_query.subquery()
        except CantFindAncestorCommitsError as e:
            log.debug(f"Couldn't find closest ancestor because {e}")
            return None

        these_benchmark_results = (
            Session.query(
                BenchmarkResult.case_id.label("case_id"),
                BenchmarkResult.context_id.label("context_id"),
            )
            .filter(BenchmarkResult.run_id == self.id)
            .subquery()
        )

        closest_benchmark_result = (
            Session.query(BenchmarkResult)
            .join(Run)
            .join(Hardware)
            # matching the case & context of any of this run's BenchmarkResults
            .join(
                these_benchmark_results,
                s.and_(
                    these_benchmark_results.c.case_id == BenchmarkResult.case_id,
                    these_benchmark_results.c.context_id == BenchmarkResult.context_id,
                ),
            )
            # only commits in this run's ancestry...
            .join(
                ancestor_commits,
                ancestor_commits.c.ancestor_id == Run.commit_id,
            )
            .filter(
                # ...but not this run's commit
                ancestor_commits.c.ancestor_id != commit.id,
                # matching the hardware of this run
                Hardware.id == self.hardware_id,
            )
            .order_by(
                # Prefer this Run's run_reason
                s.desc(Run.reason == self.reason),
                ancestor_commits.c.commit_order.desc(),
            )
            .first()
        )

        if not closest_benchmark_result:
            log.debug(
                "Could not find a matching benchmark_result in this Run's ancestry"
            )
            return None

        return closest_benchmark_result.run

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
    commit = marshmallow.fields.String(
        required=True,
        metadata={
            "description": "The 40-character commit SHA of the repo being benchmarked"
        },
    )
    repository = marshmallow.fields.String(
        required=True,
        metadata={
            "description": "The repository name (in the format `org/repo`) or the URL "
            "(in the format `https://github.com/org/repo`)"
        },
    )
    pr_number = marshmallow.fields.Integer(
        required=False,
        allow_none=True,
        metadata={
            "description": "[recommended] The number of the GitHub pull request that "
            "is running this benchmark, or `null` if it's a run on the default branch"
        },
    )
    branch = marshmallow.fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": "[not recommended] Instead of supplying `pr_number` you may "
            "supply this, the branch name in the form `org:branch`. Only do so if you "
            "know exactly what you're doing."
        },
    )


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
