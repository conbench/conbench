import flask as f
import flask_login

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import EntityExists, NotFound
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import Commit
from ..entities.run import Run, RunFacadeSchema, RunSerializer


class RunEntityAPI(ApiEndpoint):
    serializer = RunSerializer()
    schema = RunFacadeSchema()

    def _get(self, run_id):
        try:
            run = Run.one(id=run_id)
        except NotFound:
            self.abort_404_not_found()
        return run

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
        run = self._get(run_id)
        return self.serializer.one._dump(run, get_baseline_runs=True)

    @flask_login.login_required
    def put(self, run_id):
        """
        ---
        description: Edit a run.
        responses:
            "200": "RunEntityWithoutBaselines"
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
        run = self._get(run_id)
        data = self.validate(self.schema.update)
        run.update(data)
        return self.serializer.one.dump(run)

    @flask_login.login_required
    def delete(self, run_id):
        """
        ---
        description: Delete a run.
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
        benchmark_results = BenchmarkResult.all(run_id=run_id)
        for benchmark_result in benchmark_results:
            benchmark_result.delete()
        run = self._get(run_id)
        run.delete()
        return self.response_204_no_content()


class RunListAPI(ApiEndpoint):
    serializer = RunSerializer()
    schema = RunFacadeSchema()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of runs.
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
        if sha_arg := f.request.args.get("sha"):
            shas = sha_arg.split(",")
            runs = Run.search(filters=[Commit.sha.in_(shas)], joins=[Commit])
        else:
            runs = Run.all(order_by=Run.timestamp.desc(), limit=1000)
        return self.serializer.many.dump(runs)

    @flask_login.login_required
    def post(self):
        """
        ---
        description: Create a run.
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
        data = self.validate(self.schema.create)

        try:
            run = Run.create(data)
        except EntityExists as exc:
            return f.jsonify(error=409, description=str(exc)), 409

        return self.response_201_created(self.serializer.one.dump(run))


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
