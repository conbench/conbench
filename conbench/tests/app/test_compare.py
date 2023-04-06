from ...tests.api import _fixtures
from ...tests.app import _asserts


def _emsg_needle(thing, thingid):
    """
    Generate an expected error message.

    The Jinja machinery escapes the single quote (inserts the HTML entity
    notation &#39;) -- this can be changed via using the |safe operator in the
    template, but here in this error message we show user-given data so that is
    the exact case for why the 'sanitization by default' has been built into
    the templating engine
    """
    return f"cannot perform comparison: no benchmark results found for {thing} ID: &#39;{thingid}&#39;"


class TestCompareBenchmark(_asserts.GetEnforcer):
    url = "/compare/benchmarks/{}/"
    title = "Compare Benchmarks"
    redirect_on_unknown = False

    def _create(self, client):
        benchmark_id = self.create_benchmark(client)
        return f"{benchmark_id}...{benchmark_id}"

    def test_flash_messages(self, client):
        self.authenticate(client)

        response = client.get(
            "/compare/benchmarks/unknown...unknown2/", follow_redirects=True
        )
        self.assert_page(response, "Compare Benchmarks")

        assert "cannot perform comparison:" in response.text, response.text

        response = client.get("/compare/benchmarks/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmarks")
        assert "cannot perform comparison:" in response.text


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

        response = client.get(
            "/compare/batches/unknown...unknown2/", follow_redirects=True
        )
        self.assert_page(response, "Compare Batches")
        assert _emsg_needle("batch", "unknown"), response.text
        response = client.get("/compare/batches/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Batches")
        assert _emsg_needle("batch", "foo"), response.text


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
        response = client.get(
            "/compare/runs/unknown3...unknown2/", follow_redirects=True
        )
        self.assert_page(response, "Compare Runs")
        assert _emsg_needle("run", "unknown3") in response.text
        response = client.get("/compare/runs/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Runs")
        assert _emsg_needle("run", "foo") in response.text
