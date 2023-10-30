import copy
import re

import pytest

from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestBenchmarkResultList(_asserts.ListEnforcer):
    url = "/benchmark-results/"
    title = "Benchmarks"

    def _create(self, client):
        return self.create_benchmark(client)


class TestBenchmarkResultGet(_asserts.GetEnforcer):
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

    @pytest.mark.parametrize(
        "samples",
        [(1,), (3, 5), (3, 5, 7)],
    )
    def test_display_result_no_mean(self, client, samples):
        # Test that benchmark result view/page loads fine for the results that
        # have one or two multisamples only, i.e. all aggregates are undefined.
        self.authenticate(client)

        result = _fixtures.VALID_RESULT_PAYLOAD.copy()
        result["stats"] = {
            "data": samples,
            "times": [],  # key must be there as of now, validate more, change this.
            "unit": "s",
            "time_unit": "s",
            # also see https://github.com/conbench/conbench/issues/813
            # https://github.com/conbench/conbench/issues/533
            "iterations": len(samples),
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 201, resp.text
        bmr_id = resp.json["id"]
        resp = client.get(f"benchmark-results/{bmr_id}/")
        assert resp.status_code == 200, resp.text

    def test_display_result_no_mean_in_history(self, client):
        # Main goal of this test is to reproduce
        # https://github.com/conbench/conbench/issues/1155
        # before testing
        # https://github.com/conbench/conbench/pull/1167
        self.authenticate(client)
        _, bmresults = _fixtures.gen_fake_data(one_sample_no_mean=True)
        bmr_id = bmresults[3].id
        resp = client.get(f"benchmark-results/{bmr_id}/")
        assert resp.status_code == 200, resp.text

    def test_get_result_without_commit(self, client):
        self.authenticate(client)

        # Post baseline results so we try to render a plot
        for _ in range(3):
            payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
            post_response = client.post("/api/benchmark-results/", json=payload)
            assert post_response.status_code == 201

        # Post a benchmark result without a commit
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        del payload["github"]["commit"]
        payload["run_id"] = _fixtures._uuid()
        post_response = client.post("/api/benchmark-results/", json=payload)
        assert post_response.status_code == 201

        # Ensure the result doesn't have a commit
        get_response = client.get(f'/api/benchmark-results/{post_response.json["id"]}/')
        assert get_response.status_code == 200
        assert get_response.json["commit"] is None

        # Ensure the result page looks as expected
        self._assert_view(client, post_response.json["id"])

    def test_display_result_urlize_optional_info(self, client):
        # Test that benchmark result view/page loads fine for the results that
        # have optional_benchmark_info only.
        self.authenticate(client)

        result = _fixtures.VALID_RESULT_PAYLOAD.copy()
        result["optional_benchmark_info"] = {
            "single_url": "https://foo.bar",
            "list_of_single_url": ["https://foo.bar"],
            "list_of_two_urls": ["https://foo.bar", "https://foo.bar"],
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 201, resp.text
        bmr_id = resp.json["id"]
        resp = client.get(f"benchmark-results/{bmr_id}/")
        assert resp.status_code == 200, resp.text


class TestBenchmarkResultDelete(_asserts.DeleteEnforcer):
    def test_authenticated(self, client):
        benchmark_result_id = self.create_benchmark(client)

        # can get benchmark before
        self.authenticate(client)
        response = client.get(f"/benchmark-results/{benchmark_result_id}/")
        self.assert_page(response, "Benchmark")
        assert f"{benchmark_result_id[:6]}".encode() in response.data

        # delete benchmark
        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(
            f"/benchmark-results/{benchmark_result_id}/",
            data=data,
            follow_redirects=True,
        )
        self.assert_page(response, "Benchmarks")
        assert re.search(
            r"Benchmark result \w+ deleted\.", response.text, flags=re.ASCII
        )

        # cannot get benchmark after
        response = client.get(
            f"/benchmark-results/{benchmark_result_id}/", follow_redirects=True
        )
        self.assert_index_page(response)
        assert re.search(
            r"unknown benchmark result ID: \w+", response.text, flags=re.ASCII
        )

    def test_unauthenticated(self, client):
        benchmark_result_id = self.create_benchmark(client)
        self.logout(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmark-results/{benchmark_result_id}/",
            data=data,
            follow_redirects=True,
        )
        self.assert_login_page(response)

    def test_no_csrf_token(self, client):
        benchmark_result_id = self.create_benchmark(client)
        self.authenticate(client)
        data = {"delete": ["Delete"]}
        response = client.post(
            f"/benchmark-results/{benchmark_result_id}/",
            data=data,
            follow_redirects=True,
        )
        self.assert_page(response, "Benchmark")
        assert b"The CSRF token is missing." in response.data
        # TODO: test benchmark not deleted?
