import re

from ...tests.app import _asserts


class TestBenchmarkList(_asserts.ListEnforcer):
    url = "/benchmark-results/"
    title = "Benchmarks"

    def _create(self, client):
        return self.create_benchmark(client)


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/benchmark-results/{}/"
    title = "Benchmark result"

    def _create(self, client):
        return self.create_benchmark(client)

    def test_flash_message(self, client):
        self.authenticate(client)
        response = client.get("/benchmark-results/unknown/", follow_redirects=True)
        self.assert_index_page(response)
        assert re.search(
            r"unknown benchmark result ID: \w+", response.text, flags=re.ASCII
        )

    def test_legacy_route(self, client):
        # Context: https://github.com/conbench/conbench/pull/966#issuecomment-1487072612
        response = client.get(
            "/benchmarks/unknown-benchmark-result-id/", follow_redirects=True
        )
        self.assert_index_page(response)
        assert re.search(
            r"unknown benchmark result ID: \w+", response.text, flags=re.ASCII
        )


class TestBenchmarkDelete(_asserts.DeleteEnforcer):
    def test_authenticated(self, client):
        benchmark_id = self.create_benchmark(client)

        # can get benchmark before
        self.authenticate(client)
        response = client.get(f"/benchmark-results/{benchmark_id}/")
        self.assert_page(response, "Benchmark")
        assert f"{benchmark_id[:6]}".encode() in response.data

        # delete benchmark
        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(
            f"/benchmark-results/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmarks")
        assert re.search(
            r"Benchmark result \w+ deleted\.", response.text, flags=re.ASCII
        )

        # cannot get benchmark after
        response = client.get(
            f"/benchmark-results/{benchmark_id}/", follow_redirects=True
        )
        self.assert_index_page(response)
        assert re.search(
            r"unknown benchmark result ID: \w+", response.text, flags=re.ASCII
        )

    def test_unauthenticated(self, client):
        benchmark_id = self.create_benchmark(client)
        self.logout(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmark-results/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_login_page(response)

    def test_no_csrf_token(self, client):
        benchmark_id = self.create_benchmark(client)
        self.authenticate(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmark-results/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmark")
        assert b"The CSRF token is missing." in response.data
        # TODO: test benchmark not deleted?
