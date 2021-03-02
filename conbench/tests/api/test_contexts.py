import copy

from ...api._examples import _api_context_entity
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


def _expected_entity(context):
    return _api_context_entity(context.id)


def create_benchmark_summary():
    data = copy.deepcopy(VALID_PAYLOAD)
    summary = Summary.create(data)
    return summary


class TestContextGet(_asserts.GetEnforcer):
    url = "/api/contexts/{}/"
    public = True

    def _create(self):
        summary = create_benchmark_summary()
        return summary.context

    def test_get_context(self, client):
        self.authenticate(client)
        context = self._create()
        response = client.get(f"/api/contexts/{context.id}/")
        self.assert_200_ok(response, _expected_entity(context))
