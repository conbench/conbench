import pytest

from ...api._examples import _api_run_entity
from ...entities._entity import NotFound
from ...entities.run import Run
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid


def _expected_entity(run, baseline_id=None, include_baseline=True):
    parent = run.commit.get_parent_commit()
    return _api_run_entity(
        run.id,
        run.name,
        run.commit_id,
        parent.id,
        run.hardware_id,
        run.hardware.name,
        run.hardware.type,
        run.timestamp.isoformat(),
        baseline_id,
        include_baseline,
    )


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create(self, baseline=False, name=None, language=None):
        if baseline:
            contender = _fixtures.summary(
                name=name,
                sha=_fixtures.CHILD,
                language=language,
            )
            baseline = _fixtures.summary(
                name=name,
                sha=_fixtures.PARENT,
                language=language,
            )
            return contender.run, baseline.run
        else:
            contender = _fixtures.summary()
        return contender.run

    def test_get_run(self, client):
        # change anything about the context so we get only one baseline
        language, name = _uuid(), _uuid()

        self.authenticate(client)
        run, baseline = self._create(baseline=True, name=name, language=language)
        response = client.get(f"/api/runs/{run.id}/")
        self.assert_200_ok(response, _expected_entity(run, baseline.id))

    def test_get_run_should_omit_test_runs(self, client):
        # change anything about the context so we get only one baseline
        language, name = _uuid(), _uuid()

        self.authenticate(client)
        run, baseline = self._create(baseline=True, name=name, language=language)
        baseline.name = "testing"
        baseline.save()
        response = client.get(f"/api/runs/{run.id}/")
        self.assert_200_ok(response, _expected_entity(run, None))

    def test_get_run_find_correct_baseline_many_matching_contexts(self, client):
        # same context for different benchmark runs, but different benchmarks
        language, name_1, name_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        run_1, baseline_1 = self._create(baseline=True, name=name_1, language=language)
        run_2, baseline_2 = self._create(baseline=True, name=name_2, language=language)
        response = client.get(f"/api/runs/{run_1.id}/")
        self.assert_200_ok(response, _expected_entity(run_1, baseline_1.id))
        response = client.get(f"/api/runs/{run_2.id}/")
        self.assert_200_ok(response, _expected_entity(run_2, baseline_2.id))

    def test_closest_commit_different_machines(self, client):
        # same benchmarks, different machines
        name, machine_1, machine_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        contender = _fixtures.summary(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        _fixtures.summary(
            name=name,
            sha=_fixtures.PARENT,
            hardware_name=machine_2,
        )
        baseline = _fixtures.summary(
            name=name,
            sha=_fixtures.GRANDPARENT,
            hardware_name=machine_1,
        )
        _fixtures.summary(
            name=name,
            sha=_fixtures.ELDER,
            hardware_name=machine_1,
        )

        contender_run = contender.run
        baseline_run = baseline.run

        response = client.get(f"/api/runs/{contender_run.id}/")
        self.assert_200_ok(response, _expected_entity(contender_run, baseline_run.id))

    def test_closest_commit_different_machines_should_omit_test_runs(self, client):
        # same benchmarks, different machines, skip test run
        name, machine_1, machine_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        contender = _fixtures.summary(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        _fixtures.summary(
            name=name,
            sha=_fixtures.PARENT,
            hardware_name=machine_2,
        )
        testing = _fixtures.summary(
            name=name,
            sha=_fixtures.GRANDPARENT,
            hardware_name=machine_1,
        )
        baseline = _fixtures.summary(
            name=name,
            sha=_fixtures.ELDER,
            hardware_name=machine_1,
        )

        testing_run = testing.run
        testing_run.name = "testing"
        testing_run.save()

        contender_run = contender.run
        baseline_run = baseline.run

        response = client.get(f"/api/runs/{contender_run.id}/")
        self.assert_200_ok(response, _expected_entity(contender_run, baseline_run.id))


class TestRunList(_asserts.ListEnforcer):
    url = "/api/runs/"
    public = True

    def _create(self):
        _fixtures.summary(sha=_fixtures.PARENT)
        summary = _fixtures.summary()
        return summary.run

    def test_run_list(self, client):
        self.authenticate(client)
        run = self._create()
        response = client.get("/api/runs/")
        self.assert_200_ok(
            response, contains=_expected_entity(run, include_baseline=False)
        )

    def test_run_list_filter_by_sha(self, client):
        sha = _fixtures.CHILD
        self.authenticate(client)
        run = self._create()
        response = client.get(f"/api/runs/?sha={sha}")
        self.assert_200_ok(
            response, contains=_expected_entity(run, include_baseline=False)
        )

    def test_run_list_filter_by_sha_no_match(self, client):
        sha = "some unknown sha"
        self.authenticate(client)
        self._create()
        response = client.get(f"/api/runs/?sha={sha}")
        self.assert_200_ok(response, [])


class TestRunDelete(_asserts.DeleteEnforcer):
    url = "api/runs/{}/"

    def test_delete_run(self, client):
        self.authenticate(client)
        summary = _fixtures.summary()
        run_id = summary.run_id

        # can get before delete
        Run.one(id=run_id)

        # delete
        response = client.delete(f"/api/runs/{run_id}/")
        self.assert_204_no_content(response)

        # cannot get after delete
        with pytest.raises(NotFound):
            Run.one(id=run_id)
