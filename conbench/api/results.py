import logging

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
            Return benchmark results.

            Note that this endpoint does not provide on-the-fly change detection
            analysis (lookback z-score method) since the "baseline" is ill-defined.

            This endpoint implements pagination; see the `cursor` and `page_size` query
            parameters for how it works.

            For legacy reasons, this endpoint will not return results from before
            `2023-06-03 UTC`, unless the `run_id` query parameter is used to filter
            benchmark results.
        responses:
            "200": "BenchmarkList"
            "401": "401"
        parameters:
          - in: query
            name: name
            schema:
              type: string
            description: Filter results to one specific conceptual benchmark name.
          - in: query
            name: batch_id
            schema:
              type: string
            description: Filter results to one specific `batch_id`.
          - in: query
            name: run_id
            schema:
              type: string
            description: |
                Filter results to one specific `run_id`. Using this argument allows the
                response to return results from before `2023-06-03 UTC`.
          - in: query
            name: run_reason
            schema:
              type: string
            description: Filter results to one specific `run_reason`.
          - in: query
            name: cursor
            schema:
              type: string
            description: |
                Cursor for pagination. To get the first page of results, leave out this
                query parameter or submit `null`. The response's `metadata` key will
                contain a `next_page_cursor` key, which will contain the cursor to
                provide to this query parameter in order to get the next page. (If there
                is expected to be no data in the next page, the `next_page_cursor` will
                be `null`.)

                The first page will contain the `page_size` most recent results matching
                the given filter(s). Each subsequent page will have up to `page_size`
                results, going backwards in time in DB insertion order, until there are
                no more matching results or the benchmark result timestamps reach
                `2023-06-03 UTC` (if the `run_id` filter isn't used; see above).

                Implementation detail: currently, the next page's cursor value is equal
                to the ID of the earliest result in the current page. A page of results
                is therefore defined as the `page_size` latest results with an ID
                lexicographically less than the cursor value.
          - in: query
            name: page_size
            schema:
              type: integer
            description: |
                The size of pages for pagination (see `cursor`). Default 100. Max 1000.
        tags:
          - Benchmarks
        """
        filters = []
        joins = []

        if run_id_arg := f.request.args.get("run_id"):
            filters.append(BenchmarkResult.run_id == run_id_arg)
        else:
            filters.append(BenchmarkResult.timestamp >= "2023-06-03")

        if name_arg := f.request.args.get("name"):
            filters.append(Case.name == name_arg)
            joins.append(Case)

        if batch_id_arg := f.request.args.get("batch_id"):
            filters.append(BenchmarkResult.batch_id == batch_id_arg)

        if run_reason_arg := f.request.args.get("run_reason"):
            filters.append(BenchmarkResult.run_reason == run_reason_arg)

        cursor_arg = f.request.args.get("cursor")
        if cursor_arg and cursor_arg != "null":
            filters.append(BenchmarkResult.id < cursor_arg)

        page_size = f.request.args.get("page_size", 100)
        try:
            page_size = int(page_size)
            assert 1 <= page_size <= 1000
        except Exception:
            self.abort_400_bad_request(
                "page_size must be a positive integer no greater than 1000"
            )

        query = select(BenchmarkResult)
        for join in joins:
            query = query.join(join)
        query = (
            query.filter(*filters).order_by(BenchmarkResult.id.desc()).limit(page_size)
        )
        benchmark_results = current_session.scalars(query).all()

        if len(benchmark_results) == page_size:
            next_page_cursor = benchmark_results[-1].id
        else:
            # If there were fewer than page_size results, the next page should be empty
            next_page_cursor = None

        # See https://github.com/conbench/conbench/issues/999 -- for rather
        # typical queries, using orjson instead of stdlib can significantly
        # cut JSON serialization time.
        jsonbytes: bytes = orjson.dumps(
            {
                "data": [r.to_dict_for_json_api() for r in benchmark_results],
                "metadata": {"next_page_cursor": next_page_cursor},
            },
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
        # `benchmark_result.commit_repo_url` always succeeds
        conbench.metrics.COUNTER_BENCHMARK_RESULTS_INGESTED.labels(
            repourl=benchmark_result.commit_repo_url
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
