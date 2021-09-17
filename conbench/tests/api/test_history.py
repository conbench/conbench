from ...api._examples import _api_history_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(summary):
    return _api_history_entity(
        summary.id,
        summary.case_id,
        summary.context_id,
        summary.run.name,
    )


class TestHistoryGet(_asserts.GetEnforcer):
    url = "/api/history/{}/"
    public = True

    def _create(self):
        return _fixtures.summary()

    def test_get_history(self, client):
        self.authenticate(client)
        summary = self._create()
        response = client.get(f"/api/history/{summary.id}/")
        self.assert_200_ok(response, contains=_expected_entity(summary))
