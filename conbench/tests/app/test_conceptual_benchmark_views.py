import time

import pytest

import conbench.job

from ...tests.api import _fixtures
from ...tests.app import _asserts


def assert_response_is_login_page(resp):
    assert resp.status_code == 200, (resp.status_code, resp.text)
    assert "<h4>Sign in</h4>" in resp.text, resp.text
    assert '<label for="password">Password</label>' in resp.text, resp.text


benchmark_result_dict = {
    "run_id": "1",
    "batch_id": "1",
    "timestamp": "2020-11-25T21:02:44Z",
    "context": {},
    # "info": {},
    # "machine_info": {"foo": "bar"}, this should work, relax constraints
    "machine_info": _fixtures.MACHINE_INFO,
    "stats": {
        "data": [
            "0.099094",
            "0.037129",
        ],
        "unit": "s",
    },
    "tags": {
        "p1": "v1",
        "name": "fun-benchmark",
    },
}


class TestCBenchmarks(_asserts.AppEndpointTest):
    url = "/c-benchmarks"

    @pytest.mark.parametrize(
        "relpath",
        ["/c-benchmarks", "/c-benchmarks/bname", "/c-benchmarks/bname/caseid"],
    )
    def test_access_control(self, client, monkeypatch, relpath):
        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)
        assert_response_is_login_page(client.get(relpath, follow_redirects=True))

    def test_cbench_no_data(self, client):
        self.authenticate(client)
        resp = client.post("/api/benchmark-results/", json=benchmark_result_dict)
        assert resp.status_code == 201, resp.text

        conbench.job.start_jobs()
        time.sleep(10)
        conbench.job.stop_jobs_join()
