import pytest

import conbench.bmrt
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
    # something like "machine_info": {"foo": "bar"} should work, relax
    # constraints.
    "machine_info": _fixtures.MACHINE_INFO,
    # This is special repo/commit data that makes the web application use mock
    # commit data (instead of reaching out to the GitHub HTTP API). The goal
    # here is to use a commit that looks like it's on 'the default branch',
    # because only such results are entering the BMRT cache as of now.
    "github": {
        "commit": "4beb514d071c9beec69b8917b5265e77ade22fb3",
        "repository": "https://github.com/org/repo",
    },
    "stats": {
        "data": [
            "1.1",
        ],
        "unit": "s",
    },
    "tags": {
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

    def test_cache_population(self, client):
        self.authenticate(client)

        # First, insert a special result.
        resp = client.post("/api/benchmark-results/", json=benchmark_result_dict)
        assert resp.status_code == 201, f"{resp.status_code}\n{resp.text}"

        # Probe behavior without BMRT cache population.
        resp = client.get("/c-benchmarks/")
        assert "0 unique benchmark names seen across the 0 newest results" in resp.text

        # Then, force a single BMRT cache population. It's a WIP interface
        # for testing, but at least it's reasonably snappy (see timestamps
        # below):
        # [230810-09:09:46.744] [1] [conbench.job] INFO: start job: periodic BMRT cache population
        # [230810-09:09:46.745] [1] [conbench.job] INFO: start job: metrics.periodically_set_q_rem()
        # [230810-09:09:46.748] [1] [conbench.metrics] INFO: periodically_set_q_rem(): initiate
        # [230810-09:09:46.753] [1] [conbench.job] INFO: BMRT cache pop: quadratic sort loop took 0.000 s
        # [230810-09:09:46.753] [1] [conbench.job] INFO: BMRT cache pop: df constr took 0.001 s (1 time series)
        # [230810-09:09:46.753] [1] [conbench.job] INFO: BMRT cache population done (1 results, took 0.007 s)
        # [230810-09:09:46.753] [1] [conbench.job] INFO: BMRT cache: trigger next fetch in 20.000 s
        # [230810-09:09:46.753] [1] [conbench.job] INFO: stop_jobs_join(): set shutdown flag
        # [230810-09:09:46.753] [1] [conbench.job] INFO: join <Thread(bmrt-cache-refresh, started 140561314998016)>
        # [230810-09:09:46.763] [1] [conbench.job] INFO: join <Thread(metrics-gauge-set, started 140561306605312)>
        # [230810-09:09:46.799] [1] [conbench.job] INFO: all threads joined

        conbench.job.start_jobs()
        conbench.bmrt.wait_for_first_bmrt_cache_population()
        conbench.job.stop_jobs_join()

        resp = client.get("/c-benchmarks/")
        assert "fun-benchmark" in resp.text
        assert "1 unique benchmark names seen across the 1 newest results" in resp.text

    @pytest.mark.parametrize(
        "relpath",
        ["/c-benchmarks", "/c-benchmarks/bname", "/c-benchmarks/bname/caseid"],
    )
    def test_sub_pages_deliver_200_before_population(self, client, relpath):
        # Confirms that these views do not crash before cache population. So
        # far they show "0 results"; this can be misleading. Maybe later add a
        # nice info/error message (in practice, users will only very
        # infrequently see that state: right after deploying a new Conbench
        # version there is a brief time span where the cache is not yet
        # populated)

        # wipe cache
        conbench.bmrt.reinit()

        self.authenticate(client)
        resp = client.get(relpath, follow_redirects=True)
        assert resp.status_code == 200, f"{resp.status_code}\n{resp.text}"

    def test_c_bench_landing_behavior(self, client):
        # Make sure cache is empty.
        conbench.bmrt.reinit()
        self.authenticate(client)
        resp = client.get("/c-benchmarks/")
        assert resp.status_code == 200, f"{resp.status_code}\n{resp.text}"
        assert "0 unique benchmark names seen across" in resp.text

    @pytest.mark.parametrize(
        "relpath",
        ["/c-benchmarks/bname", "/c-benchmarks/bname/caseid"],
    )
    def test_sub_pages_show_error(self, client, relpath):
        # Make sure cache is empty.
        conbench.bmrt.reinit()
        self.authenticate(client)
        # Test for black-on-white err so far. It's not good UX yet.
        resp = client.get(relpath, follow_redirects=True)
        assert resp.status_code == 200, f"{resp.status_code}\n{resp.text}"

        assert "benchmark name not known: `bname`" in resp.text
