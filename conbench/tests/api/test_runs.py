import copy

from ...api._examples import _api_run_entity
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


def _expected_entity(run):
    return _api_run_entity(
        run.id,
        run.machine_id,
        run.commit_id,
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

    def test_benchmark_list(self, client):
        self.authenticate(client)
        run = self._create()
        response = client.get("/api/runs/")
        self.assert_200_ok(response, contains=_expected_entity(run))
