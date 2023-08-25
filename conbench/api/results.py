import datetime
import logging
from typing import Optional

import flask as f
import flask_login
import orjson
from sqlalchemy import select

import conbench.metrics
from conbench.dbsession import current_session

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.benchmark_result import (
    BenchmarkResult,
    BenchmarkResultFacadeSchema,
    BenchmarkResultSerializer,
    BenchmarkResultValidationError,
)
from ..entities.case import Case
from ._resp import json_response_for_byte_sequence, resp400

log = logging.getLogger(__name__)


class BenchmarkValidationMixin:
    def validate_benchmark(self, schema):
        return self.validate(schema)


class BenchmarkEntityAPI(ApiEndpoint, BenchmarkValidationMixin):
    serializer = BenchmarkResultSerializer()
    schema = BenchmarkResultFacadeSchema()

    def _get(self, benchmark_result_id):
        try:
            benchmark_result = BenchmarkResult.one(id=benchmark_result_id)
        except NotFound:
            self.abort_404_not_found()
        return benchmark_result

    @maybe_login_required
    def get(self, benchmark_result_id):
        """
        ---
        description: |
            Get a specific benchmark result.
        responses:
            "200": "BenchmarkEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_result_id)
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def put(self, benchmark_result_id):
        """
        ---
        description: Edit a benchmark result.
        responses:
            "200": "BenchmarkEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        requestBody:
            content:
                application/json:
                    schema: BenchmarkResultUpdate
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_result_id)
        data = self.validate_benchmark(self.schema.update)
        benchmark_result.update(data)
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def delete(self, benchmark_result_id):
        """
        ---
        description: Delete a benchmark result.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_result_id)
        benchmark_result.delete()
        return self.response_204_no_content()


class BenchmarkListAPI(ApiEndpoint, BenchmarkValidationMixin):
    serializer = BenchmarkResultSerializer()
    schema = BenchmarkResultFacadeSchema()

    @maybe_login_required
    def get(self) -> f.Response:
        """
        ---
        description: |
            Return a JSON array of benchmark results.

            Note that this endpoint does not provide on-the-fly change
            detection analysis (lookback z-score method).

            Behavior at the time of writing (subject to change):

            Benchmark results are usually returned in order of their
            timestamp property (user-given benchmark start time), newest first.

            When no argument is provided, the last 1000 benchmark results
            are emitted.

            The `run_id` argument can be provided to obtain benchmark
            results for one or more specific runs. This attempts to fetch
            all associated benchmark results from the database and tries
            to return them all in a single response; use that with caution:
            keep the number of run_ids low or equal to, unless you know better.

            The `run_reason` argument can be provided to obtain benchmark
            results for a specific run reason. Currently, this will return 30000
            results if no limit is defined.

            The `days` argument can be provided to limit the benchmark results from last `N` days.
            This can be combined with other arguments, except `run_id`.

            The `limit` argument can be provided to limit the number of results.
            This can be combined with other arguments, except `run_id`.

        responses:
            "200": "BenchmarkList"
            "401": "401"
        parameters:
          - in: query
            name: name
            schema:
              type: string
          - in: query
            name: batch_id
            schema:
              type: string
          - in: query
            name: run_id
            schema:
              type: string
          - in: query
            name: run_reason
            schema:
              type: string
          - in: query
            name: days
            schema:
              type: integer
          - in: query
            name: limit
            schema:
              type: integer
        tags:
          - Benchmarks
        """
        # Note(JP): "case name" is the conceptual benchmark name. Interesting,
        # so this is like asking "give me results for this benchmark".

        # setting filters for days parameter
        days_filters: list = []
        if days_arg := f.request.args.get("days"):
            min_time = datetime.datetime.now(
                datetime.timezone.utc
            ).date() - datetime.timedelta(days=days_arg)
            days_filters = [
                BenchmarkResult.timestamp >= min_time,
            ]

        # setting limit value
        limit: Optional[int] = None
        if limit_arg := f.request.args.get("limit"):
            limit = limit_arg

        if name_arg := f.request.args.get("name"):
            # TODO: This needs a limit, and sorting behavior.
            benchmark_results = BenchmarkResult.search(
                filters=[Case.name == name_arg] + days_filters,
                joins=[Case],
                limit=limit,
            )

        elif batch_id_arg := f.request.args.get("batch_id"):
            batch_ids = batch_id_arg.split(",")
            benchmark_results = BenchmarkResult.search(
                filters=[BenchmarkResult.batch_id.in_(batch_ids)] + days_filters,
                limit=limit,
            )

        elif run_id_arg := f.request.args.get("run_id"):
            run_ids = run_id_arg.split(",")
            if len(run_ids) > 5:
                return resp400(
                    "it is currently not allowed to set more than five "
                    "run_id values; consider making separate requests (see "
                    "issue 978)"
                )

            benchmark_results = current_session.scalars(
                select(BenchmarkResult).where(BenchmarkResult.run_id.in_(run_ids))
            ).all()

        elif run_reason_arg := f.request.args.get("run_reason"):
            if not limit:
                limit = 30000
            benchmark_results = BenchmarkResult.search(
                filters=[BenchmarkResult.run_reason == run_reason_arg] + days_filters,
                order_by=BenchmarkResult.timestamp.desc(),
                limit=limit,
            )

        else:
            if not days_filters:
                limit = 1000
            benchmark_results = BenchmarkResult.all(
                filter_args=days_filters,
                order_by=BenchmarkResult.timestamp.desc(),
                limit=limit,
            )

        # See https://github.com/conbench/conbench/issues/999 -- for rather
        # typical queries, using orjson instead of stdlib can significantly
        # cut JSON serialization time.

        jsonbytes: bytes = orjson.dumps(
            [r.to_dict_for_json_api() for r in benchmark_results],
            option=orjson.OPT_INDENT_2,
        )

        return json_response_for_byte_sequence(jsonbytes, 200)

    @flask_login.login_required
    def post(self) -> f.Response:
        """
        ---
        description:
            Submit a BenchmarkResult within a specific Run.

            If the Run (as defined by its Run ID) is not known yet in the
            database it gets implicitly created, using details provided in this
            request. If the Run ID matches an existing run, then the rest of
            the fields describing the Run (such as name, hardware info, ...}
            are silently ignored.
        responses:
            "201": "BenchmarkResultCreated"
            "400": "400"
            "401": "401"
        requestBody:
            content:
                application/json:
                    schema: BenchmarkResultCreate
        tags:
          - Benchmarks
        """
        # Here it should be easy to make `data` have a precise type (that mypy
        # can use) based on the schema that we validate against.
        data = self.validate_benchmark(self.schema.create)

        try:
            benchmark_result = BenchmarkResult.create(data)
        except BenchmarkResultValidationError as exc:
            return resp400(str(exc))

        # Rely on the idea that the lookup
        # `benchmark_result.commit.repo_url` always succeeds
        conbench.metrics.COUNTER_BENCHMARK_RESULTS_INGESTED.labels(
            repourl=benchmark_result.associated_commit_repo_url
        ).inc()
        return self.response_201_created(self.serializer.one.dump(benchmark_result))


benchmark_entity_view = BenchmarkEntityAPI.as_view("benchmark")
benchmark_list_view = BenchmarkListAPI.as_view("benchmarks")

# Phase these out, at some point.
# https://github.com/conbench/conbench/issues/972
rule(
    "/benchmarks/",
    view_func=benchmark_list_view,
    methods=["GET", "POST"],
)
rule(
    "/benchmarks/<benchmark_result_id>/",
    view_func=benchmark_entity_view,
    methods=["GET", "DELETE", "PUT"],
)

# Towards the more explicit route path naming":
# https://github.com/conbench/conbench/issues/972
rule(
    "/benchmark-results/",
    view_func=benchmark_list_view,
    methods=["GET", "POST"],
)
rule(
    "/benchmark-results/<benchmark_result_id>/",
    view_func=benchmark_entity_view,
    methods=["GET", "DELETE", "PUT"],
)
spec.components.schema(
    "BenchmarkResultCreate", schema=BenchmarkResultFacadeSchema.create
)
spec.components.schema(
    "BenchmarkResultUpdate", schema=BenchmarkResultFacadeSchema.update
)
