import flask as f
import flask_login

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.benchmark_result import (
    BenchmarkFacadeSchema,
    BenchmarkResult,
    BenchmarkResultSerializer,
)
from ..entities.case import Case
from ..entities.history import set_z_scores


class BenchmarkValidationMixin:
    def validate_benchmark(self, schema):
        return self.validate(schema)


class BenchmarkEntityAPI(ApiEndpoint, BenchmarkValidationMixin):
    serializer = BenchmarkResultSerializer()
    schema = BenchmarkFacadeSchema()

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
        description: Get a benchmark.
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
        set_z_scores([benchmark_result])
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def put(self, benchmark_id):
        """
        ---
        description: Edit a benchmark.
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
                    schema: BenchmarkUpdate
        tags:
          - Benchmarks
        """
        benchmark_result = self._get(benchmark_id)
        data = self.validate_benchmark(self.schema.update)
        benchmark_result.update(data)
        set_z_scores([benchmark_result])
        return self.serializer.one.dump(benchmark_result)

    @flask_login.login_required
    def delete(self, benchmark_id):
        """
        ---
        description: Delete a benchmark.
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
    schema = BenchmarkFacadeSchema()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of benchmarks.
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
        if name_arg := f.request.args.get("name"):
            benchmark_results = BenchmarkResult.search(
                filters=[Case.name == name_arg],
                joins=[Case],
            )
            # Since there's no limit on the number of BenchmarkResults, we could take
            # forever calculating z-scores with no caching advantage. So don't do that.
            for benchmark_result in benchmark_results:
                benchmark_result.z_score = None
        elif batch_id_arg := f.request.args.get("batch_id"):
            batch_ids = batch_id_arg.split(",")
            benchmark_results = BenchmarkResult.search(
                filters=[BenchmarkResult.batch_id.in_(batch_ids)]
            )
            set_z_scores(benchmark_results)
        elif run_id_arg := f.request.args.get("run_id"):
            run_ids = run_id_arg.split(",")
            benchmark_results = BenchmarkResult.search(
                filters=[BenchmarkResult.run_id.in_(run_ids)]
            )
            set_z_scores(benchmark_results)
        else:
            benchmark_results = BenchmarkResult.all(
                order_by=BenchmarkResult.timestamp.desc(), limit=500
            )
            # Setting z-scores takes too long for this one too.
            for benchmark_result in benchmark_results:
                benchmark_result.z_score = None

        return self.serializer.many.dump(benchmark_results)

    @flask_login.login_required
    def post(self):
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
            "201": "BenchmarkCreated"
            "400": "400"
            "401": "401"
        requestBody:
            content:
                application/json:
                    schema: BenchmarkCreate
        tags:
          - Benchmarks
        """
        data = self.validate_benchmark(self.schema.create)
        benchmark_result = BenchmarkResult.create(data)
        set_z_scores([benchmark_result])
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
spec.components.schema("BenchmarkCreate", schema=BenchmarkFacadeSchema.create)
spec.components.schema("BenchmarkUpdate", schema=BenchmarkFacadeSchema.update)
