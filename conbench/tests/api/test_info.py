from ...api._examples import _api_info_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(info):
    return _api_info_entity(info.id)


def create_info():
    summary = _fixtures.summary()
    return summary.info


class TestInfoGet(_asserts.GetEnforcer):
    url = "/api/info/{}/"
    public = True

    def _create(self):
        return create_info()

    def test_get_info(self, client):
        self.authenticate(client)
        info = self._create()
        response = client.get(f"/api/info/{info.id}/")
        self.assert_200_ok(response, _expected_entity(info))


class TestInfoList(_asserts.ListEnforcer):
    url = "/api/info/"
    public = True

    def _create(self):
        return create_info()

    def test_info_list(self, client):
        self.authenticate(client)
        info = self._create()
        response = client.get("/api/info/")
        self.assert_200_ok(response, contains=_expected_entity(info))
