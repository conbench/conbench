import copy

from ...tests.api import _fixtures
from ...tests.app import _asserts


def create_benchmark(client):
    # also create a benchmark with a different name & batch_id
    other = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    other["batch_id"] = other["batch_id"] + "-other"
    other["tags"]["name"] = other["tags"]["name"] + "-other"
    other["timestamp"] = "2019-11-25T21:02:42.706806+00:00"
    client.post("/api/benchmarks/", json=other)

    # create a benchmark
    data = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    response = client.post("/api/benchmarks/", json=data)
    new_id = response.json["id"]
    batch_id = response.json["batch_id"]
    return new_id, batch_id


class TestBatch(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id, batch_id = create_benchmark(client)
        self.logout(client)
        return new_id, batch_id

    def _assert_view(self, client, batch_id):
        response = client.get(f"/batches/{batch_id}/")
        self.assert_page(response, "Batch")
        assert f"{batch_id}</li>".encode() in response.data

    def test_batch_get_authenticated(self, client):
        _, batch_id = self._create(client)
        self.authenticate(client)
        self._assert_view(client, batch_id)

    def test_batch_get_unauthenticated(self, client):
        _, batch_id = self._create(client)
        self.logout(client)
        self._assert_view(client, batch_id)

    def test_batch_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/batches/unknown/", follow_redirects=True)
        self.assert_page(response, "Batch")
