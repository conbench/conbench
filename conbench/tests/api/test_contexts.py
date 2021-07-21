from ...api._examples import _api_context_entity
from ...tests.api import _asserts
from ...tests.api import _fixtures


def _expected_entity(context):
    return _api_context_entity(context.id)


class TestContextGet(_asserts.GetEnforcer):
    url = "/api/contexts/{}/"
    public = True

    def _create(self):
        summary = _fixtures.create_benchmark_summary()
        return summary.context

    def test_get_context(self, client):
        self.authenticate(client)
        context = self._create()
        response = client.get(f"/api/contexts/{context.id}/")
        self.assert_200_ok(response, _expected_entity(context))
