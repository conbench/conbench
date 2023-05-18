import logging

import copy
from ...tests.api import _fixtures
from ...tests.app import _asserts


log = logging.getLogger(__name__)


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


class TestCompareBenchmarkResults(_asserts.GetEnforcer):
    url = "/compare/benchmark-results/{}/"
    title = "Compare Benchmark Results"
    redirect_on_unknown = False

    def _create(self, client):
        benchmark_result_id = self.create_benchmark(client)
        return f"{benchmark_result_id}...{benchmark_result_id}"

    def test_flash_messages(self, client):
        self.authenticate(client)

        response = client.get(
            "/compare/benchmarks/unknown...unknown2/", follow_redirects=True
        )
        self.assert_page(response, "Compare Benchmark Results")

        assert "cannot perform comparison:" in response.text, response.text

        response = client.get("/compare/benchmarks/foo...bar/", follow_redirects=True)
        self.assert_page(response, "Compare Benchmark Results")
        assert "cannot perform comparison:" in response.text


class TestCompareBenchmarks(_asserts.AppEndpointTest):
    url = "/compare/benchmarks/{}/"
    title = "Compare Benchmark Results"
    redirect_on_unknown = False

    def _create(self, client):
        benchmark_result_id = self.create_benchmark(client)
        return f"{benchmark_result_id}...{benchmark_result_id}"

    def test_redirects(self, client):
        self.authenticate(client)

        response = client.get(
            "/compare/benchmarks/unknown...unknown2/", follow_redirects=True
        )
        assert "/compare/benchmark-results/unknown...unknown2/" in response.request.url
        assert any(
            [
                "/compare/benchmarks/unknown...unknown2/" == res.request.path
                for res in response.history
            ]
        )
        assert "cannot perform comparison:" in response.text, response.text

        response = client.get("/compare/benchmarks/foo...bar/", follow_redirects=True)
        assert "/compare/benchmark-results/foo...bar/" in response.request.url
        assert any(
            [
                "/compare/benchmarks/foo...bar/" == res.request.path
                for res in response.history
            ]
        )
        assert "cannot perform comparison:" in response.text


class TestCompareRuns(_asserts.GetEnforcer):
    url = "/compare/runs/{}/"
    title = "Compare Runs"
    redirect_on_unknown = False

    def _create(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_RESULT_PAYLOAD["run_id"]
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

    @staticmethod
    def _post_result(client, run_id, language) -> None:
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        payload["run_id"] = run_id
        payload["context"]["benchmark_language"] = language
        response = client.post("/api/benchmarks/", json=payload)
        assert response.status_code == 201, response.text

    def test_mismatching_runs(self, client):
        self.authenticate(client)

        # Some benchmark results are comparable, some aren't
        self._post_result(client, "run1", "python")
        self._post_result(client, "run1", "R")
        self._post_result(client, "run2", "python")
        self._post_result(client, "run2", "C++")

        # Ensure the run page looks as expected
        response = client.get("/compare/runs/run1...run2/")
        self.assert_page(response, "Compare Runs")
        log.info(response.text)
        assert not response.text
