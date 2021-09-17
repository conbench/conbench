from ...api._examples import _api_context_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(context):
    return _api_context_entity(context.id)


def create_context():
    summary = _fixtures.summary()
    return summary.context


class TestContextGet(_asserts.GetEnforcer):
    url = "/api/contexts/{}/"
    public = True

    def _create(self):
        return create_context()

    def test_get_context(self, client):
        self.authenticate(client)
        context = self._create()
        response = client.get(f"/api/contexts/{context.id}/")
        self.assert_200_ok(response, _expected_entity(context))


class TestContextList(_asserts.ListEnforcer):
    url = "/api/contexts/"
    public = True

    def _create(self):
        return create_context()

    def test_context_list(self, client):
        self.authenticate(client)
        context = self._create()
        response = client.get("/api/contexts/")
        self.assert_200_ok(response, contains=_expected_entity(context))
