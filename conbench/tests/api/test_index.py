import datetime
import importlib.metadata as importlib_metadata

from ...api._examples import API_INDEX
from ...tests.api import _asserts

__version__ = importlib_metadata.version("conbench")


class TestIndexList(_asserts.ListEnforcer):
    url = "/api/"

    def test_api_index(self, client):
        self.authenticate(client)
        response = client.get("/api/")
        self.assert_200_ok(response, API_INDEX)


class TestAPI(_asserts.ApiEndpointTest):
    def test_unknown_api_endpoint(self, client):
        response = client.get("/api/foo")
        self.assert_404_not_found(response)

    def test_ping(self, client):
        response = client.get("/api/ping/")
        data = response.json
        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert set(data) == {"date", "conbench_version", "alembic_version"}
        assert str(datetime.datetime.today().year) in data["date"]
        assert data["conbench_version"] == __version__
