import pytest

from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestIndex(_asserts.ListEnforcer):
    url = "/"
    title = "Home"

    def _create(self, client):
        self.create_benchmark(client)
        return _fixtures.VALID_PAYLOAD["run_id"]

    def test_unknown_route(self, client):
        response = client.get("/foo/")
        self.assert_404_not_found(response)

    def test_both_routes(self, client):
        run_id = self._create(client)
        self.authenticate(client)

        response = client.get("/")
        self.assert_index_page(response)
        assert run_id.encode() in response.data

        response = client.get("/index/")
        self.assert_index_page(response)
        assert run_id.encode() in response.data


class TestCBenchmarks(_asserts.AppEndpointTest):
    url = "/c-benchmarks"

    def test_public_data_off(self, client, monkeypatch):
        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)
        response = client.get(self.url, follow_redirects=True)
        assert b"Sign In" in response.data, response.data
