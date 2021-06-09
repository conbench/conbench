from ...tests.app import _asserts
from ...tests.api import _fixtures


def create_benchmark(client):
    response = client.post("/api/benchmarks/", json=_fixtures.VALID_PAYLOAD)
    new_id = response.json["id"]
    return new_id


class TestBenchmarks(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        return new_id

    def _assert_view(self, client, new_id):
        response = client.get("/benchmarks/")
        self.assert_page(response, "Benchmarks")
        assert f"{new_id}".encode() in response.data

    def test_benchmark_list_authenticated(self, client):
        new_id = self._create(client)
        self.authenticate(client)
        self._assert_view(client, new_id)

    def test_benchmark_list_unauthenticated(self, client):
        new_id = self._create(client)
        self.logout(client)
        self._assert_view(client, new_id)


class TestBenchmark(_asserts.AppEndpointTest):
    def _create(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        return new_id

    def _assert_view(self, client, new_id):
        response = client.get(f"/benchmarks/{new_id}/")
        self.assert_page(response, "Benchmark")
        assert f"{new_id}</li>".encode() in response.data

    def test_benchmark_get_authenticated(self, client):
        new_id = self._create(client)
        self.authenticate(client)
        self._assert_view(client, new_id)

    def test_benchmark_get_unauthenticated(self, client):
        new_id = self._create(client)
        self.logout(client)
        self._assert_view(client, new_id)

    def test_benchmark_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/benchmarks/unknown/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting benchmark." in response.data

    def test_benchmark_delete_authenticated(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)

        # can get benchmark before
        response = client.get(f"/benchmarks/{new_id}/")
        self.assert_page(response, "Benchmark")
        assert f"{new_id}</li>".encode() in response.data

        # delete benchmark
        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(
            f"/benchmarks/{new_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmarks")
        assert b"Benchmark deleted." in response.data

        # cannot get benchmark after
        response = client.get(f"/benchmarks/{new_id}/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting benchmark." in response.data

    def test_benchmark_delete_unauthenticated(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        self.logout(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmarks/{new_id}/", data=data, follow_redirects=True
        )
        self.assert_login_page(response)

    def test_benchmark_delete_no_csrf_token(self, client):
        self.authenticate(client)
        new_id = create_benchmark(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmarks/{new_id}/", data=data, follow_redirects=True
        )
        self.assert_page(response, "Benchmark")
        assert b"The CSRF token is missing." in response.data
        # TODO: test benchmark not deleted?
