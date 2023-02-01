import logging
from datetime import timezone
from typing import Optional

import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

import conbench.util

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
    # `timestamp`  is never set by API clients, i.e. the
    # `server_default=s.sql.func.now()` is always taking effect. That also
    # means that this property reflects the point in time of DB insertion (that
    # should be documented in the API schema for Run objects). A more explicit
    # way to code that would be in the create() method. The point in time by
    # convention is stored in UTC _without_ timezone information. Is a wrong
    # point in time stored when `s.sql.func.now()` returns a non-UTC tz-aware
    # timestamp on a DB server that does not have its system time in UTC? That
    # should not happen, as is hopefully confirmed by the test
    # `test_auto_generated_run_timestamp_value()`.
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    # tz-naive timestamp expected to refer to UTC time.
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

    def get_baseline_run(
        self,
        commit_limit: int = 20,
        on_default_branch: bool = False,
        case_id: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> Optional["Run"]:
        """Return the closest ancestor of this Run, where the ancestor run:

        - is in the last ``commit_limit`` commits of this Run's commit ancestry
        - is on the default branch, if on_default_branch is True (else on any branch)
        - shares this Run's hardware
        - has a BenchmarkResult with the given case_id/context_id, if those are given
        - if they aren't given, has a BenchmarkResult with the case_id/context_id of
          *any* of this Run's BenchmarkResults

        Returns None if there are no matches. This could be a false negative if
        ``commit_limit`` is too low (though note that the query takes longer with a
        higher ``commit_limit``).

        If there are multiple matches, prefer a Run with the same reason as this Run,
        and then find the latest commit, finally tiebreaking by latest Run.timestamp.
        """
        from ..entities.benchmark_result import BenchmarkResult

        this_commit: Commit = self.commit
        try:
            ancestor_commits = (
                this_commit.commit_ancestry_query
                # don't count this run's commit
                .filter(Commit.id != this_commit.id)
                .order_by(s.desc("commit_order"))
                .limit(commit_limit)
                .subquery()
            )
        except CantFindAncestorCommitsError as e:
            log.debug(f"Couldn't get_baseline_run() because {e}")
            return None

        closest_run_id_query = (
            Session.query(BenchmarkResult.run_id)
            .join(Run)
            .join(Hardware)
            .join(ancestor_commits, ancestor_commits.c.ancestor_id == Run.commit_id)
            .filter(Hardware.id == self.hardware_id)
        )

        if on_default_branch:
            closest_run_id_query = closest_run_id_query.filter(
                ancestor_commits.c.on_default_branch.is_(True)
            )

        # Filter to the correct case(s)/context(s)
        if case_id and context_id:
            # filter to the given case/context
            closest_run_id_query = closest_run_id_query.filter(
                BenchmarkResult.case_id == case_id,
                BenchmarkResult.context_id == context_id,
            )
        else:
            # filter to *any* case/context attached to this Run
            these_benchmark_results = (
                Session.query(BenchmarkResult.case_id, BenchmarkResult.context_id)
                .filter(BenchmarkResult.run_id == self.id)
                .subquery()
            )
            closest_run_id_query = closest_run_id_query.join(
                these_benchmark_results,
                s.and_(
                    these_benchmark_results.c.case_id == BenchmarkResult.case_id,
                    these_benchmark_results.c.context_id == BenchmarkResult.context_id,
                ),
            )

        closest_run_id = closest_run_id_query.order_by(
            s.desc(Run.reason == self.reason),  # Prefer this Run's run_reason,
            ancestor_commits.c.commit_order.desc(),  # then latest commit,
            Run.timestamp.desc(),  # then latest Run timestamp
        ).first()

        if not closest_run_id:
            log.debug(
                "Could not find a matching benchmark_result in this Run's ancestry"
            )
            return None

        return Run.get(closest_run_id)

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
            "timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                run.timestamp
            ),
            "finished_timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                run.finished_timestamp
            )
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
    @marshmallow.pre_load
    def change_pr_number_empty_string_to_none(self, data, **kwargs):
        if "pr_number" in data:
            data["pr_number"] = data["pr_number"] or None

        return data

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
    "finished_timestamp": (
        "A datetime string indicating the time at which the run finished. "
        "Expected to be in ISO 8601 notation. Timezone-aware notation "
        "recommended. Timezone-naive strings are interpreted in UTC. "
        "Fractions of seconds can be provided but are not returned by the "
        "API. Example value: 2022-11-25T22:02:42Z"
    ),
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

    @marshmallow.post_load
    def recalc_finished_time(self, data, **kwargs):
        curdt = data.get("finished_timestamp")

        if curdt is None:
            return data

        data["finished_timestamp"] = conbench.util.dt_shift_to_utc(curdt)
        return data

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
    # `AwareDateTime` with `default_timezone` set to UTC: naive datetimes are
    # set this timezone.
    finished_timestamp = marshmallow.fields.AwareDateTime(
        required=False,
        format="iso",
        default_timezone=timezone.utc,
        metadata={
            "description": field_descriptions["finished_timestamp"],
        },
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

    @marshmallow.post_load
    def recalc_finished_time(self, data, **kwargs):
        curdt = data.get("finished_timestamp")

        if curdt is None:
            return data

        data["finished_timestamp"] = conbench.util.dt_shift_to_utc(curdt)
        return data


class RunFacadeSchema:
    create = _RunFacadeSchemaCreate()
    update = _RunFacadeSchemaUpdate()
