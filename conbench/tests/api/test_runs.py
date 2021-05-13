import copy
import urllib
import uuid

from ...api._examples import _api_run_entity
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


def _expected_entity(run, baseline_id=None):
    return _api_run_entity(
        run.id,
        run.commit_id,
        run.machine_id,
        run.timestamp.isoformat(),
        baseline_id,
    )


def create_benchmark_summary(parent_sha=None):
    data = copy.deepcopy(VALID_PAYLOAD)
    if parent_sha:
        data["github"]["commit"] = parent_sha
        data["stats"]["run_id"] = uuid.uuid4().hex
    summary = Summary.create(data)
    return summary


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create(self, baseline=False):
        contender = create_benchmark_summary()
        if baseline:
            parent_sha = "4beb514d071c9beec69b8917b5265e77ade22fb3"
            baseline = create_benchmark_summary(parent_sha)
            return contender.run, baseline.run
        return contender.run

    def test_get_run(self, client):
        self.authenticate(client)
        run, baseline = self._create(baseline=True)
        response = client.get(f"/api/runs/{run.id}/")
        self.assert_200_ok(response, _expected_entity(run, baseline.id))


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

    def test_run_list_filter_by_sha_and_machine(self, client):
        sha = "02addad336ba19a654f9c857ede546331be7b631"
        self.authenticate(client)
        run = self._create()
        args = {"sha": sha, "machine_id": run.machine_id}
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, contains=_expected_entity(run))

    def test_run_list_filter_by_sha_and_machine_no_match(self, client):
        sha = "02addad336ba19a654f9c857ede546331be7b631"
        self.authenticate(client)
        self._create()
        args = {"sha": sha, "machine_id": "some other machine id"}
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, [])
