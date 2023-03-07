import flask as f

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.history import HistorySerializer, get_history_for_benchmark


class HistoryEntityAPI(ApiEndpoint):
    serializer = HistorySerializer()

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
        # TODO: think about the case where samples if of zero length. Can this
        # happen? If it can happen: which response would we want to emit to the
        # HTTP client? An empty array, or something more convenient?
        try:
            samples = get_history_for_benchmark(benchmark_result_id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()

        # if performance is a concern then https://pypi.org/project/orjson/
        # promises to be among the fastest for serializing python dataclass
        # instances into JSON. Note: wrap this into an array if there is just 1
        # sample, for consistency (clients can expect an array).
        return f.jsonify([s._dict_for_api_json() for s in samples])


history_entity_view = HistoryEntityAPI.as_view("history")

rule(
    "/history/<benchmark_id>/",
    view_func=history_entity_view,
    methods=["GET"],
)
