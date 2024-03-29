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
        assert set(data) == {"date", "alembic_version", "commit"}
        assert str(datetime.datetime.today().year) in data["date"]
        # full git commit hashes can be expected to be 40 characters long.
        # if/when this ever changes then this test can change, too.
        assert len(data["commit"]) == 40

    def test_wipe(self, client):
        # This endpoint is here for convenience in local development/testing.
        response = client.get("/api/wipe-db")
        assert response.status_code == 200

    def test_json_err(self, client):
        # This endpoint is here for convenience in local development/testing.
        response = client.get("/api/raise-httperr")
        assert response.status_code == 400
        for k in ("code", "name", "description"):
            assert response.json[k]

    def test_traceback_in_500(self, client):
        # This endpoint is here for convenience in local development/testing.
        response = client.get("/api/raise-unexpected")
        assert response.status_code == 500
        assert "traceback" in response.text.lower()
