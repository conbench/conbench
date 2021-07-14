import copy

from ...tests.api import _fixtures
from ...tests.app import _asserts


def create_benchmark(client):
    # also create a benchmark with a different name & run_id
    other = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    other["run_id"] = other["run_id"] + "-other"
    other["tags"]["name"] = other["tags"]["name"] + "-other"
    other["timestamp"] = "2019-11-25T21:02:42.706806+00:00"
    client.post("/api/benchmarks/", json=other)

    # create a benchmark
    data = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    response = client.post("/api/benchmarks/", json=data)
    new_id = response.json["id"]
    run_id = response.json["run_id"]
    return new_id, run_id


class TestRun(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id, run_id = create_benchmark(client)
        self.logout(client)
        return new_id, run_id

    def _assert_view(self, client, run_id):
        response = client.get(f"/runs/{run_id}/")
        self.assert_page(response, "Run")
        assert f"{run_id}</li>".encode() in response.data

    def test_run_get_authenticated(self, client):
        _, run_id = self._create(client)
        self.authenticate(client)
        self._assert_view(client, run_id)

    def test_run_get_unauthenticated(self, client):
        _, run_id = self._create(client)
        self.logout(client)
        self._assert_view(client, run_id)

    def test_run_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/runs/unknown/", follow_redirects=True)
        self.assert_page(response, "Run")
