from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestCompareBenchmark(_asserts.GetEnforcer):
    url = "/compare/benchmarks/{}/"
    title = "Compare Benchmarks"
    redirect_on_unknown = False

    def _create(self, client):
        benchmark_id = self.create_benchmark(client)
        return f"{benchmark_id}...{benchmark_id}"

    def test_flash_messages(self, client):
        self.authenticate(client)

        response = client.get("/compare/benchmarks/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmarks")
        assert b"Invalid contender and baseline." in response.data

        response = client.get("/compare/benchmarks/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmarks")
        assert b"Data is still collecting (or failed)." in response.data


class TestCompareBatches(_asserts.GetEnforcer):
    url = "/compare/batches/{}/"
    title = "Compare Batches"
    redirect_on_unknown = False

    def _create(self, client):
        self.create_benchmark(client)
        batch_id = _fixtures.VALID_PAYLOAD["batch_id"]
        return f"{batch_id}...{batch_id}"

    def test_flash_messages(self, client):
        self.authenticate(client)

        response = client.get("/compare/batches/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Batches")
        assert b"Invalid contender and baseline." in response.data

        response = client.get("/compare/batches/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Batches")
        assert b"Data is still collecting (or failed)." in response.data


class TestCompareRuns(_asserts.GetEnforcer):
    url = "/compare/runs/{}/"
    title = "Compare Runs"
    redirect_on_unknown = False

    def _create(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_PAYLOAD["run_id"]
        return f"{run_id}...{run_id}"

    def test_flash_messages(self, client):
        self.authenticate(client)

        response = client.get("/compare/runs/unknown/", follow_redirects=True)
        self.assert_page(response, "Compare Runs")
        assert b"Invalid contender and baseline." in response.data

        response = client.get("/compare/runs/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Runs")
        assert b"Data is still collecting (or failed)." in response.data
