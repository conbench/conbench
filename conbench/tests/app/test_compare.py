from ...tests.api import _fixtures
from ...tests.app import _asserts


def create_benchmark(client):
    response = client.post("/api/benchmarks/", json=_fixtures.VALID_PAYLOAD)
    new_id = response.json["id"]
    return new_id


class TestCompareBenchmark(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        return new_id

    def _assert_view(self, client, new_id):
        response = client.get(f"/compare/benchmarks/{new_id}...{new_id}/")
        self.assert_page(response, "Compare Benchmarks")
        assert f"{new_id}".encode() in response.data

    def test_compare_authenticated(self, client):
        new_id = self._create(client)
        self.authenticate(client)
        self._assert_view(client, new_id)

    def test_compare_unauthenticated(self, client):
        new_id = self._create(client)
        self.logout(client)
        self._assert_view(client, new_id)

    def test_compare_unknown(self, client):
        self.authenticate(client)
        response = client.get("/compare/benchmarks/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmarks")
        assert b"Invalid contender and baseline." in response.data

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/compare/benchmarks/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmarks")
        assert b"Data is still collecting (or failed)." in response.data


class TestCompareBatches(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        return new_id

    def _assert_view(self, client, batch_id):
        response = client.get(f"/compare/batches/{batch_id}...{batch_id}/")
        self.assert_page(response, "Compare Batches")
        assert f"{batch_id}".encode() in response.data

    def test_compare_authenticated(self, client):
        batch_id = _fixtures.VALID_PAYLOAD["batch_id"]
        self._create(client)
        self.authenticate(client)
        self._assert_view(client, batch_id)

    def test_compare_unauthenticated(self, client):
        batch_id = _fixtures.VALID_PAYLOAD["batch_id"]
        self._create(client)
        self.logout(client)
        self._assert_view(client, batch_id)

    def test_compare_unknown(self, client):
        self.authenticate(client)
        response = client.get("/compare/batches/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Batches")
        assert b"Invalid contender and baseline." in response.data

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/compare/batches/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Batches")
        assert b"Data is still collecting (or failed)." in response.data


class TestCompareRuns(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        return new_id

    def _assert_view(self, client, run_id):
        response = client.get(f"/compare/runs/{run_id}...{run_id}/")
        self.assert_page(response, "Compare Runs")
        assert f"{run_id}".encode() in response.data

    def test_compare_authenticated(self, client):
        run_id = _fixtures.VALID_PAYLOAD["run_id"]
        self._create(client)
        self.authenticate(client)
        self._assert_view(client, run_id)

    def test_compare_unauthenticated(self, client):
        run_id = _fixtures.VALID_PAYLOAD["run_id"]
        self._create(client)
        self.logout(client)
        self._assert_view(client, run_id)

    def test_compare_unknown(self, client):
        self.authenticate(client)
        response = client.get("/compare/runs/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Runs")
        assert b"Invalid contender and baseline." in response.data

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/compare/runs/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Runs")
        assert b"Data is still collecting (or failed)." in response.data
