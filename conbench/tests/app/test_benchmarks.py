from ...tests.app import _asserts


class TestBenchmarkList(_asserts.ListEnforcer):
    url = "/benchmarks/"
    title = "Benchmarks"

    def _create(self, client):
        return self.create_benchmark(client)


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/benchmarks/{}/"
    title = "Benchmark"

    def _create(self, client):
        return self.create_benchmark(client)

    def test_flash_message(self, client):
        self.authenticate(client)
        response = client.get("/benchmarks/unknown/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting benchmark." in response.data


class TestBenchmarkDelete(_asserts.DeleteEnforcer):
    def test_authenticated(self, client):
        benchmark_id = self.create_benchmark(client)

        # can get benchmark before
        self.authenticate(client)
        response = client.get(f"/benchmarks/{benchmark_id}/")
        self.assert_page(response, "Benchmark")
        assert f"{benchmark_id}</li>".encode() in response.data

        # delete benchmark
        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(
            f"/benchmarks/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmarks")
        assert b"Benchmark deleted." in response.data

        # cannot get benchmark after
        response = client.get(f"/benchmarks/{benchmark_id}/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting benchmark." in response.data

    def test_unauthenticated(self, client):
        benchmark_id = self.create_benchmark(client)
        self.logout(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmarks/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_login_page(response)

    def test_no_csrf_token(self, client):
        benchmark_id = self.create_benchmark(client)
        self.authenticate(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmarks/{benchmark_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmark")
        assert b"The CSRF token is missing." in response.data
        # TODO: test benchmark not deleted?
