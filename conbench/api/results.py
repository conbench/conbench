import logging

import flask as f
import flask_login
import orjson
from sqlalchemy import select

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..db import Session
from ..entities._entity import NotFound
from ..entities.benchmark_result import (
    BenchmarkResult,
    BenchmarkResultFacadeSchema,
    BenchmarkResultSerializer,
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

    def _get(self, benchmark_id):
        try:
            benchmark_result = BenchmarkResult.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        return benchmark_result

    @maybe_login_required
    def get(self, benchmark_id):
        """
        ---
        description: |
            Get a specific benchmark result.

            The "z_score" key in the response is deprecated and only returns null.
        responses:
            "200": "BenchmarkEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_id
            in: path
            schema:
                type: string
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_id)
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def put(self, benchmark_id):
        """
        ---
        description: Edit a benchmark result.
        responses:
            "200": "BenchmarkEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_id
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
        benchmark_result = self._get(benchmark_id)
        data = self.validate_benchmark(self.schema.update)
        benchmark_result.update(data)
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def delete(self, benchmark_id):
        """
        ---
        description: Delete a benchmark result.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_id
            in: path
            schema:
                type: string
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_id)
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
        tags:
          - Benchmarks
        """
        # Note(JP): "case name" is the conceptual benchmark name. Interesting,
        # so this is like asking "give me results for this benchmark".
        if name_arg := f.request.args.get("name"):
            # TODO: This needs a limit, and sorting behavior.
            benchmark_results = BenchmarkResult.search(
                filters=[Case.name == name_arg],
                joins=[Case],
            )

        elif batch_id_arg := f.request.args.get("batch_id"):
            batch_ids = batch_id_arg.split(",")
            benchmark_results = BenchmarkResult.search(
                filters=[BenchmarkResult.batch_id.in_(batch_ids)]
            )

        elif run_id_arg := f.request.args.get("run_id"):
            # Note(JP): https://github.com/conbench/conbench/issues/978 Given
            # Conbench's data model we want to limit the number of run_ids that
            # can be provided here. Maybe to 1, maybe to 5. Querying results
            # for 100 runs (seen in practice) is for now difficult to support.
            run_ids = run_id_arg.split(",")
            if len(run_ids) > 5:
                log.warning(
                    "suspicious query /api/benchmarks for many run_ids -- see conbench/conbench/issues/978"
                )

            benchmark_results = Session.scalars(
                select(BenchmarkResult).where(BenchmarkResult.run_id.in_(run_ids))
            ).all()

        else:
            benchmark_results = BenchmarkResult.all(
                order_by=BenchmarkResult.timestamp.desc(), limit=1000
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

        # Note(JP): this next block inspects and mutates `tags`, with the goal
        # that all keys are non-empty strings, and all values are non-empty
        # strings. See
        # https://github.com/conbench/conbench/pull/948#discussion_r1149090197
        # for background. Summary of current desired behavior: primitive value
        # types are accepted (string, boolean, float, int; non-string values
        # are converted to string before DB insertion). Other value types
        # (array -> list, object -> dict) lead to request rejection.
        tags = data["tags"]
        # Iterate over a copy of key/value pairs.
        for key, value in list(tags.items()):
            # In JSON, a key is always of type string. We rely on this, codify
            # this invariant.
            assert isinstance(key, str)

            # An empty string is a valid JSON key. Do not allow this.
            if len(key) == 0:
                return resp400("tags: zero-length string as key is not allowed")

            # For now, be liberal in what we accept. Do not consider empty
            # string or None values for the case permutation (do not store
            # those in the DB, drop these key/value pairs). This is documented
            # in the API spec. Maybe in the future we want to reject such
            # requests with a Bad Request response.
            if value == "" or value is None:
                log.warning("drop tag key/value pair: `%s`, `%s`", key, value)
                # Remove current key/value pair, proceed with next key. This
                # mutates the dictionary `data["tags"]`; for keeping this a
                # sane operation the loop iterates over a copy of key/value
                # pairs.
                del tags[key]
                continue

            # Note(JP): this code path should go away after we adjust our
            # client tooling to not send numeric values anymore.
            if isinstance(value, (int, float, bool)):
                # I think we first want to adjust some client tooling before
                # enabling this log line:
                # log.warning("stringify case parameter value: `%s`, `%s`", key, value)
                # Replace value, proceed with next key.
                tags[key] = str(value)
                continue

            # This should be logically equivalent with the value being either
            # of type dict or of type list.
            if not isinstance(value, str):
                # Emit Bad Request response..
                return resp400(
                    "tags: bad value type for key `{key}`, JSON object and array is not allowed`"
                )

        # At this point, assume that data["tags"] is a flat dictionary with
        # keys being non-empty strings, and values being non-empty strings.

        # Note(JP): in the future this will also raise further validation
        # errors that are to be exposed via a 400 response to the HTTP client
        benchmark_result = BenchmarkResult.create(data)

        return self.response_201_created(self.serializer.one.dump(benchmark_result))


benchmark_entity_view = BenchmarkEntityAPI.as_view("benchmark")
benchmark_list_view = BenchmarkListAPI.as_view("benchmarks")

rule(
    "/benchmarks/",
    view_func=benchmark_list_view,
    methods=["GET", "POST"],
)
rule(
    "/benchmarks/<benchmark_id>/",
    view_func=benchmark_entity_view,
    methods=["GET", "DELETE", "PUT"],
)
spec.components.schema(
    "BenchmarkResultCreate", schema=BenchmarkResultFacadeSchema.create
)
spec.components.schema(
    "BenchmarkResultUpdate", schema=BenchmarkResultFacadeSchema.update
)
