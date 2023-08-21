import dataclasses
import datetime
import functools
from typing import Dict, List, Optional

import flask as f
import flask_login

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import Commit
from ..entities.run import RunFacadeSchema, RunSerializer
from ..util import short_commit_msg


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
            days).
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
