from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.history import HistorySerializer, get_history
from ..entities.summary import Summary


class HistoryEntityAPI(ApiEndpoint):
    serializer = HistorySerializer()

    def _get(self, benchmark_id):
        try:
            summary = Summary.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        return get_history(
            summary.case_id,
            summary.context_id,
            summary.run.machine.hash,
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
