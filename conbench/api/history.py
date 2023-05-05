import orjson

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.history import get_history_for_benchmark
from ._resp import json_response_for_byte_sequence


class HistoryEntityAPI(ApiEndpoint):
    @maybe_login_required
    def get(self, benchmark_result_id):
        """
        ---
        description: Get benchmark history.
        responses:
            "200": "HistoryList"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
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
            samples = get_history_for_benchmark(benchmark_result_id=benchmark_result_id)
        except NotFound:
            self.abort_404_not_found()

        # Note: wrap this into an array if there is just 1 sample, for
        # consistency (clients expect an array).
        jsonbytes: bytes = orjson.dumps(
            [s._dict_for_api_json() for s in samples],
            option=orjson.OPT_INDENT_2,
        )
        return json_response_for_byte_sequence(jsonbytes, 200)


history_entity_view = HistoryEntityAPI.as_view("history")

rule(
    "/history/<benchmark_result_id>/",
    view_func=history_entity_view,
    methods=["GET"],
)
