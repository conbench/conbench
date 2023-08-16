import datetime
from typing import Dict, List, Optional, Tuple

import flask as f
import flask_login

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import Commit
from ..entities.run import RunFacadeSchema, RunSerializer


def get_all_run_info(
    min_time: datetime.datetime,
    max_time: datetime.datetime,
    commit_hashes: Optional[List[str]] = None,
) -> List[Tuple[BenchmarkResult, int, bool]]:
    """Get info about each run in a time range.

    Query the database for all benchmark results (optionally filtered to certain commit
    hashes) in a time range, and return a list of tuples, each corresponding to one
    run_id. The tuples contain:

    - the earliest BenchmarkResult for that run (by its timestamp)
    - the number of benchmark results seen for that run
    - whether any benchmark results are "failed" in that run

    This powers the "list runs" API endpoint and the "recent runs" list on the home page.
    """
    run_info: Dict[str, Tuple[BenchmarkResult, int, bool]] = {}  # keyed by run_id

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
        if run_id not in run_info:
            run_info[run_id] = (result, 1, result.is_failed)
        else:
            old_result, old_count, old_failed = run_info[run_id]
            run_info[run_id] = (
                result if result.timestamp < old_result.timestamp else old_result,
                old_count + 1,
                old_failed or result.is_failed,
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
        description: Get a list of runs from the last 30 days of benchmark results.
        responses:
            "200": "RunList"
            "401": "401"
        parameters:
          - in: query
            name: sha
            schema:
              type: string
        tags:
          - Runs
        """
        sha_arg: Optional[str] = f.request.args.get("sha")
        commit_hashes = sha_arg.split(",") if sha_arg else None

        return [
            self.serializer.one._dump(result, get_baseline_runs=False)
            for result, _, _ in get_all_run_info(
                min_time=datetime.datetime.utcnow() - datetime.timedelta(days=30),
                max_time=datetime.datetime.utcnow(),
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
