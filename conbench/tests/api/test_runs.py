import copy
import urllib

from ...api._examples import _api_run_entity
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


def _expected_entity(run):
    return _api_run_entity(
        run.id,
        run.commit_id,
        run.context_id,
        run.machine_id,
        run.timestamp.isoformat(),
    )


def create_benchmark_summary():
    data = copy.deepcopy(VALID_PAYLOAD)
    summary = Summary.create(data)
    return summary


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create(self):
        summary = create_benchmark_summary()
        return summary.run

    def test_get_run(self, client):
        self.authenticate(client)
        run = self._create()
        response = client.get(f"/api/runs/{run.id}/")
        self.assert_200_ok(response, _expected_entity(run))


class TestRunList(_asserts.ListEnforcer):
    url = "/api/runs/"
    public = True

    def _create(self):
        summary = create_benchmark_summary()
        return summary.run

    def test_run_list(self, client):
        self.authenticate(client)
        run = self._create()
        response = client.get("/api/runs/")
        self.assert_200_ok(response, contains=_expected_entity(run))

    def test_run_list_filter_by_run_keys(self, client):
        sha = "02addad336ba19a654f9c857ede546331be7b631"
        self.authenticate(client)
        run = self._create()
        args = {
            "sha": sha,
            "machine_id": run.machine_id,
            "context_id": run.context_id,
        }
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, contains=_expected_entity(run))

    def test_run_list_filter_by_run_keys_no_match(self, client):
        sha = "02addad336ba19a654f9c857ede546331be7b631"
        self.authenticate(client)
        run = self._create()
        args = {
            "sha": sha,
            "machine_id": "some other machine id",
            "context_id": run.context_id,
        }
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, [])
