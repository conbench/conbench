import flask as f
import flask_login

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.case import Case
from ..entities.distribution import set_z_scores
from ..entities.summary import BenchmarkFacadeSchema, Summary, SummarySerializer


class BenchmarkValidationMixin:
    def validate_benchmark(self, schema):
        return self.validate(schema)


class BenchmarkEntityAPI(ApiEndpoint, BenchmarkValidationMixin):
    serializer = SummarySerializer()

    def _get(self, benchmark_id):
        try:
            summary = Summary.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        return summary

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
        summary = self._get(benchmark_id)
        set_z_scores([summary])
        return self.serializer.one.dump(summary)

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
        summary = self._get(benchmark_id)
        summary.delete()
        return self.response_204_no_content()


class BenchmarkListAPI(ApiEndpoint, BenchmarkValidationMixin):
    serializer = SummarySerializer()
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
        name = f.request.args.get("name")
        batch_id = f.request.args.get("batch_id")
        run_id = f.request.args.get("run_id")
        if name:
            summaries = Summary.search(
                filters=[Case.name == name],
                joins=[Case],
            )
            # TODO: cannot currently compute z_score on an arbitrary
            # list of summaries - assumes same machine/sha/repository.
            for summary in summaries:
                summary.z_score = 0
        elif batch_id:
            summaries = Summary.all(batch_id=batch_id)
            set_z_scores(summaries)
        elif run_id:
            summaries = Summary.all(run_id=run_id)
            set_z_scores(summaries)
        else:
            summaries = Summary.all(order_by=Summary.timestamp.desc(), limit=500)
            # TODO: cannot currently compute z_score on an arbitrary
            # list of summaries - assumes same machine/sha/repository.
            for summary in summaries:
                summary.z_score = 0
        return self.serializer.many.dump(summaries)

    @flask_login.login_required
    def post(self):
        """
        ---
        description: Create a benchmark.
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
        summary = Summary.create(data)
        set_z_scores([summary])
        return self.response_201_created(self.serializer.one.dump(summary))


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
    methods=["GET", "DELETE"],
)
spec.components.schema("BenchmarkCreate", schema=BenchmarkFacadeSchema.create)
