from ...api._examples import _api_history_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(benchmark_result):
    return _api_history_entity(
        benchmark_result.id,
        benchmark_result.case_id,
        benchmark_result.context_id,
        benchmark_result.run.name,
    )


class TestHistoryGet(_asserts.GetEnforcer):
    url = "/api/history/{}/"
    public = True

    def _create(self):
        return _fixtures.benchmark_result()

    def test_get_history(self, client):
        self.authenticate(client)
        benchmark_result = self._create()
        response = client.get(f"/api/history/{benchmark_result.id}/")
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result))
