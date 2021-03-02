import copy

from ...tests.api.test_benchmarks import VALID_PAYLOAD
from ...tests.app import _asserts


def create_benchmark(client):
    # also create a benchmark with a different name & batch_id
    other = copy.deepcopy(VALID_PAYLOAD)
    other["stats"]["batch_id"] = other["stats"]["batch_id"] + "-other"
    other["tags"]["name"] = other["tags"]["name"] + "-other"
    other["stats"]["timestamp"] = "2019-11-25T21:02:42.706806+00:00"
    client.post("/api/benchmarks/", json=other)

    # create a benchmark
    data = copy.deepcopy(VALID_PAYLOAD)
    response = client.post("/api/benchmarks/", json=data)
    new_id = response.json["id"]
    batch_id = response.json["stats"]["batch_id"]
    return new_id, batch_id


class TestSeriesList(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        create_benchmark(client)
        self.logout(client)

    def _assert_view(self, client):
        response = client.get("/series/")
        self.assert_page(response, "Series")
        assert '<h3 class="panel-title">file-write'.encode() in response.data

    def test_series_list_authenticated(self, client):
        self._create(client)
        self.authenticate(client)
        self._assert_view(client)

    def test_series_list_unauthenticated(self, client):
        self._create(client)
        self.logout(client)
        self._assert_view(client)


class TestSeries(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        create_benchmark(client)
        self.logout(client)

    def _assert_view(self, client):
        response = client.get(f"/series/file-write/")
        self.assert_page(response, "Series")
        assert "file-write</li>".encode() in response.data

    def test_series_get_authenticated(self, client):
        self._create(client)
        self.authenticate(client)
        self._assert_view(client)

    def test_series_get_unauthenticated(self, client):
        self._create(client)
        self.logout(client)
        self._assert_view(client)

    def test_series_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/series/unknown/", follow_redirects=True)
        self.assert_page(response, "Series")
