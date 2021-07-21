import urllib

from ...api._examples import _api_run_entity
from ...tests.api import _asserts
from ...tests.api import _fixtures
from ...tests.helpers import _uuid


def _expected_entity(run, baseline_id=None):
    return _api_run_entity(
        run.id,
        run.commit_id,
        run.machine_id,
        run.timestamp.isoformat(),
        baseline_id,
    )


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create(self, baseline=False):
        if baseline:
            # change anything about the context so we get only one baseline
            language = _uuid()
            contender = _fixtures.create_benchmark_summary(
                sha=_fixtures.CHILD,
                language=language,
                run_id=_uuid(),
            )
            baseline = _fixtures.create_benchmark_summary(
                sha=_fixtures.PARENT,
                language=language,
                run_id=_uuid(),
            )
            return contender.run, baseline.run
        else:
            contender = _fixtures.create_benchmark_summary()
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
        summary = _fixtures.create_benchmark_summary()
        return summary.run

    def test_run_list(self, client):
        self.authenticate(client)
        run = self._create()
        response = client.get("/api/runs/")
        self.assert_200_ok(response, contains=_expected_entity(run))

    def test_run_list_filter_by_sha_and_machine(self, client):
        sha = _fixtures.CHILD
        self.authenticate(client)
        run = self._create()
        args = {"sha": sha, "machine_id": run.machine_id}
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, contains=_expected_entity(run))

    def test_run_list_filter_by_sha_and_machine_no_match(self, client):
        sha = _fixtures.CHILD
        self.authenticate(client)
        self._create()
        args = {"sha": sha, "machine_id": "some other machine id"}
        args = urllib.parse.urlencode(args)
        response = client.get(f"/api/runs/?{args}")
        self.assert_200_ok(response, [])
