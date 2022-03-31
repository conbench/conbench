from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.benchmark_result import BenchmarkResult
from ..entities.history import HistorySerializer, get_history


class HistoryEntityAPI(ApiEndpoint):
    serializer = HistorySerializer()

    def _get(self, benchmark_id):
        try:
            benchmark_result = BenchmarkResult.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        return get_history(
            benchmark_result.case_id,
            benchmark_result.context_id,
            benchmark_result.run.hardware.hash,
        )

    @maybe_login_required
    def get(self, benchmark_id):
        """
        ---
        description: Get benchmark history.
        responses:
            "200": "HistoryList"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_id
            in: path
            schema:
                type: string
        tags:
          - History
        """
        history = self._get(benchmark_id)
        return self.serializer.many.dump(history)


history_entity_view = HistoryEntityAPI.as_view("history")

rule(
    "/history/<benchmark_id>/",
    view_func=history_entity_view,
    methods=["GET"],
)
