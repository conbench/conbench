import dataclasses
import datetime
import functools
from typing import Dict, List, Optional, Sequence

import flask as f
import flask_login
import marshmallow
import sqlalchemy as s

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..dbsession import current_session
from ..entities._entity import EntitySerializer
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import CantFindAncestorCommitsError, Commit, CommitSerializer
from ..entities.hardware import Hardware, HardwareSerializer
from ..util import short_commit_msg, tznaive_dt_to_aware_iso8601_for_api


@dataclasses.dataclass
class RunAggregate:
    """Aggregated information about a run."""

    earliest_result: BenchmarkResult
    result_count: int
    any_result_failed: bool

    def update(self, new_result: BenchmarkResult):
        """Update the aggregate information based on a new result."""
        self.earliest_result = (
            new_result
            if new_result.timestamp < self.earliest_result.timestamp
            else self.earliest_result
        )
        self.result_count += 1
        self.any_result_failed = self.any_result_failed or new_result.is_failed

    @functools.cached_property
    def display_commit_time(self) -> str:
        return self.earliest_result.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    @functools.cached_property
    def display_commit_msg(self) -> str:
        return short_commit_msg(
            self.earliest_result.commit.message if self.earliest_result.commit else ""
        )


def get_all_run_info(
    min_time: datetime.datetime,
    max_time: datetime.datetime,
    commit_hashes: Optional[List[str]] = None,
) -> List[RunAggregate]:
    """Get info about each run in a time range.

    Query the database for all benchmark results (optionally filtered to certain commit
    hashes) in a time range, and return a list of RunAggregates, each corresponding to
    one run_id.

    This powers the "list runs" API endpoint and the "recent runs" list on the home
    page.

    Note: At the min_time boundary, the count is permanently wrong (single run partially
    represented in DB query result, true for just one of many runs). That's fine, the UI
    does not claim real-time truth in that regard. In the vast majority of the cases we
    get a correct result count per run.
    """
    run_info: Dict[str, RunAggregate] = {}  # keyed by run_id

    joins = []
    filters = [
        BenchmarkResult.timestamp >= min_time,
        BenchmarkResult.timestamp <= max_time,
    ]
    if commit_hashes:
        joins.append(Commit)
        filters.append(Commit.sha.in_(commit_hashes))

    for result in BenchmarkResult.search(filters=filters, joins=joins):
        run_id = result.run_id
        if run_id in run_info:
            run_info[run_id].update(result)
        else:
            run_info[run_id] = RunAggregate(
                earliest_result=result,
                result_count=1,
                any_result_failed=result.is_failed,
            )

    return list(run_info.values())


@dataclasses.dataclass
class _CandidateBaselineSearchResult:
    """Information about the search for a candidate baseline run, and the result of the
    search.
    """

    # An error message, if the search failed.
    error: Optional[str] = None

    # The run ID of the candidate baseline run, if the search succeeded.
    baseline_run_id: Optional[str] = None

    # The commit hashes that were skipped during the search, if the search succeeded.
    commits_skipped: Optional[Sequence[str]] = None

    def _dict_for_api_json(self) -> dict:
        return dataclasses.asdict(self)


def _search_for_baseline_run(
    contender_run_id: str,
    contender_run_reason: Optional[str],
    contender_hardware_checksum: str,
    baseline_commit: Optional[Commit],
    commit_limit: int = 20,
) -> _CandidateBaselineSearchResult:
    """Search for and return information about a baseline run of a contender run, where
    the baseline run:

    - is on the given baseline_commit, or in its git ancestry (up to
        ``commit_limit`` commits ago)
    - matches the contender run's hardware checksum
    - has a BenchmarkResult with the case_id/context_id of any of the contender
        run's BenchmarkResults

    Always returns a _CandidateBaselineSearchResult, and if there are no matches for
    some reason, that reason will be in its ``error`` attribute. If there are multiple
    matches, prefer a baseline run with the same reason as the contender run, and then
    use the baseline run with the most-recent commit, finally tiebreaking by choosing
    the baseline run with the latest BenchmarkResult.timestamp.
    """
    from ..entities.benchmark_result import BenchmarkResult

    if not baseline_commit:
        return _CandidateBaselineSearchResult(
            error="this baseline commit type does not exist for this run"
        )

    try:
        ancestor_commits = (
            baseline_commit.commit_ancestry_query.order_by(s.desc("commit_order"))
            .limit(commit_limit)
            .subquery()
        )
    except CantFindAncestorCommitsError as e:
        return _CandidateBaselineSearchResult(
            error=f"could not find the baseline commit's ancestry because {e}"
        )

    baseline_run_query = (
        s.select(
            BenchmarkResult.run_id,
            Commit.sha,
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
        )
        .select_from(BenchmarkResult)
        .join(Hardware, Hardware.id == BenchmarkResult.hardware_id)
        .join(Commit, Commit.id == BenchmarkResult.commit_id)
        .join(ancestor_commits, ancestor_commits.c.ancestor_id == Commit.id)
        .filter(
            Hardware.hash == contender_hardware_checksum,
            BenchmarkResult.run_id != contender_run_id,
        )
        .order_by(
            # Prefer this Run's run_reason,
            s.desc(BenchmarkResult.run_reason == contender_run_reason),
            ancestor_commits.c.commit_order.desc(),  # then latest commit,
            BenchmarkResult.timestamp.desc(),  # then latest BenchmarkResult timestamp
        )
    )
    matching_benchmark_results = current_session.execute(baseline_run_query).all()

    valid_cases_and_contexts = set(
        row.tuple()
        for row in current_session.execute(
            s.select(BenchmarkResult.case_id, BenchmarkResult.context_id).filter(
                BenchmarkResult.run_id == contender_run_id
            )
        ).all()
    )

    for row in matching_benchmark_results:
        baseline_run_id, baseline_commit_hash, case_id, context_id = row.tuple()
        if (case_id, context_id) in valid_cases_and_contexts:
            # Continue onward with the first one that matches a case_id/context_id
            # of this run
            break
    else:
        return _CandidateBaselineSearchResult(
            error="no matching baseline run was found"
        )

    # Figure out a list of commits that were skipped in the search for a baseline
    commit_hashes_searched = current_session.scalars(
        s.select(Commit.sha)
        .select_from(ancestor_commits)
        .join(Commit, Commit.id == ancestor_commits.c.ancestor_id)
        .order_by(ancestor_commits.c.commit_order.desc())
    ).all()
    index_of_baseline = commit_hashes_searched.index(baseline_commit_hash)
    commits_skipped = commit_hashes_searched[:index_of_baseline]

    return _CandidateBaselineSearchResult(
        baseline_run_id=baseline_run_id, commits_skipped=commits_skipped
    )


def get_candidate_baseline_runs(
    contender_benchmark_result: "BenchmarkResult",
) -> Dict[str, dict]:
    """Given a benchmark result from a contender run, return information about a few
    different candidate baseline runs, including on the parent commit, fork-point
    commit, and head-of-default-branch commit.

    See docstring of _search_for_baseline_run() for how these are found.
    """
    contender_commit = contender_benchmark_result.commit
    candidates: Dict[str, _CandidateBaselineSearchResult] = {}

    # The direct, single parent in the git graph
    if not contender_commit:
        candidates["parent"] = _CandidateBaselineSearchResult(
            error="the contender run is not connected to the git graph"
        )
    else:
        candidates["parent"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_parent_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_hardware_checksum=contender_benchmark_result.hardware.hash,
        )

    # If this is a PR run, the PR's fork point commit on the default branch
    if not contender_commit:
        candidates["fork_point"] = _CandidateBaselineSearchResult(
            error="the contender run is not connected to the git graph"
        )
    elif contender_commit.sha == contender_commit.fork_point_sha:
        candidates["fork_point"] = _CandidateBaselineSearchResult(
            error="the contender run is already on the default branch"
        )
    else:
        candidates["fork_point"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_fork_point_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_hardware_checksum=contender_benchmark_result.hardware.hash,
        )

    # The latest commit on the default branch that Conbench knows about
    query = s.select(Commit).filter(Commit.sha == Commit.fork_point_sha)

    # TODO: how do we filter by repository if there's no commit?
    # (For now we just choose the latest commit of any repository.)
    if contender_commit:
        query = query.filter(Commit.repository == contender_commit.repository)

    latest_commit = current_session.scalars(
        query.order_by(s.desc(Commit.timestamp)).limit(1)
    ).first()
    candidates["latest_default"] = _search_for_baseline_run(
        baseline_commit=latest_commit,
        contender_run_id=contender_benchmark_result.run_id,
        contender_run_reason=contender_benchmark_result.run_reason,
        contender_hardware_checksum=contender_benchmark_result.hardware.hash,
    )

    return {
        candidate_type: candidate._dict_for_api_json()
        for candidate_type, candidate in candidates.items()
    }


class _Serializer(EntitySerializer):
    def _dump(
        self, benchmark_result: "BenchmarkResult", get_baseline_runs: bool = False
    ):
        if benchmark_result.commit:
            commit_dict = CommitSerializer().one.dump(benchmark_result.commit)
            commit_dict.pop("links", None)
        else:
            commit_dict = None

        hardware_dict = HardwareSerializer().one.dump(benchmark_result.hardware)
        hardware_dict.pop("links", None)
        out_dict = {
            "id": benchmark_result.run_id,
            "tags": benchmark_result.run_tags,
            "reason": benchmark_result.run_reason,
            "timestamp": tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.timestamp
            ),
            "commit": commit_dict,
            "hardware": hardware_dict,
        }
        if get_baseline_runs:
            out_dict["candidate_baseline_runs"] = get_candidate_baseline_runs(
                benchmark_result
            )
        return out_dict


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class _RunFacadeSchemaCreate(marshmallow.Schema):
    """Deprecated."""


class _RunFacadeSchemaUpdate(marshmallow.Schema):
    """Deprecated."""


class RunFacadeSchema:
    create = _RunFacadeSchemaCreate()
    update = _RunFacadeSchemaUpdate()


class RunEntityAPI(ApiEndpoint):
    serializer = RunSerializer()
    schema = RunFacadeSchema()

    @maybe_login_required
    def get(self, run_id):
        """
        ---
        description: |
            Get a run and information about its candidate baseline runs.

            The `"candidate_baseline_runs"` key in the response contains information
            about up to three candidate baseline runs. Each baseline run corresponds to
            a different candidate baseline commit, detailed below. If a baseline run is
            not found for that commit, the response will detail why in the `"error"`
            key. If a baseline run is found, its ID will be returned in the
            `"baseline_run_id"` key.

            The three candidate baseline commits are:

            - the parent commit of the contender run's commit (`"parent"`)
            - if the contender run is on a PR branch, the default-branch commit that the
              PR branch forked from (`"fork_point"`)
            - if the contender run is on a PR branch, the latest commit on the default
              branch that has benchmark results (`"latest_default"`)

            When searching for a baseline run, each matching baseline run must:

            - be on the respective baseline commit, or in its git ancestry
            - match the contender run's hardware
            - have a benchmark result with the `case_id`/`context_id` of any of the
              contender run's benchmark results

            If there are multiple matches, prefer a baseline run with the same reason as
            the contender run, and then use the baseline run with the most-recent
            commit, finally tiebreaking by choosing the baseline run with the latest run
            timestamp.

            If any commits in the git ancestry were skipped to find a matching baseline
            run, those commit hashes will be returned in the `"commits_skipped"` key.
        responses:
            "200": "RunEntityWithBaselines"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        tags:
          - Runs
        """
        any_result = BenchmarkResult.first(run_id=run_id)
        if not any_result:
            self.abort_404_not_found()
        return self.serializer.one._dump(any_result, get_baseline_runs=True)

    @flask_login.login_required
    def put(self, run_id):
        """
        ---
        description: Deprecated. This endpoint is a no-op, despite returning a 200.
        responses:
            "200": "RunCreated"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        requestBody:
            content:
                application/json:
                    schema: RunUpdate
        tags:
          - Runs
        """
        return {}

    @flask_login.login_required
    def delete(self, run_id):
        """
        ---
        description: Deprecated. This endpoint is a no-op, despite returning a 204.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        tags:
          - Runs
        """
        return self.response_204_no_content()


class RunListAPI(ApiEndpoint):
    serializer = RunSerializer()
    schema = RunFacadeSchema()

    @maybe_login_required
    def get(self):
        """
        ---
        description: |
            Get a list of runs from the last few days of benchmark results (default 14
            days; no more than 30 days).
        responses:
            "200": "RunList"
            "401": "401"
        parameters:
          - in: query
            name: sha
            schema:
              type: string
          - in: query
            name: days
            schema:
              type: integer
        tags:
          - Runs
        """
        sha_arg: Optional[str] = f.request.args.get("sha")
        commit_hashes = sha_arg.split(",") if sha_arg else None

        days_arg: Optional[int] = f.request.args.get("days")
        days = int(days_arg) if days_arg else 14
        if days > 30:
            self.abort_400_bad_request("days must be no more than 30")

        return [
            self.serializer.one._dump(run.earliest_result, get_baseline_runs=False)
            for run in get_all_run_info(
                min_time=datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=days),
                max_time=datetime.datetime.now(datetime.timezone.utc),
                commit_hashes=commit_hashes,
            )
        ]

    @flask_login.login_required
    def post(self):
        """
        ---
        description: Deprecated. This endpoint is a no-op, despite returning a 201.
        responses:
            "201": "RunCreated"
            "400": "400"
            "401": "401"
        requestBody:
            content:
                application/json:
                    schema: RunCreate
        tags:
          - Runs
        """
        return self.response_201_created({})


run_entity_view = RunEntityAPI.as_view("run")
run_list_view = RunListAPI.as_view("runs")

rule(
    "/runs/",
    view_func=run_list_view,
    methods=["GET", "POST"],
)
rule(
    "/runs/<run_id>/",
    view_func=run_entity_view,
    methods=["GET", "DELETE", "PUT"],
)
spec.components.schema("RunCreate", schema=RunFacadeSchema.create)
spec.components.schema("RunUpdate", schema=RunFacadeSchema.update)
