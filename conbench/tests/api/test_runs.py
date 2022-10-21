import pytest

from ...api._examples import _api_run_entity
from ...entities._entity import NotFound
from ...entities.run import Run
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid


def _expected_entity(run, baseline_id=None, include_baseline=True):
    parent = run.commit.get_parent_commit()
    has_errors = False
    return _api_run_entity(
        run.id,
        run.name,
        run.reason,
        run.commit_id,
        parent.id if parent else None,
        run.hardware_id,
        run.hardware.name,
        run.hardware.type,
        run.timestamp.isoformat(),
        baseline_id,
        include_baseline,
        has_errors,
        run.finished_timestamp.isoformat() if run.finished_timestamp else None,
        run.info,
        run.error_info,
        run.error_type,
    )


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create(self, baseline=False, name=None, language=None):
        if baseline:
            contender = _fixtures.benchmark_result(
                name=name,
                sha=_fixtures.CHILD,
                language=language,
            )
            baseline = _fixtures.benchmark_result(
                name=name,
                sha=_fixtures.PARENT,
                language=language,
            )
            return contender.run, baseline.run
        else:
            contender = _fixtures.benchmark_result()
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
        baseline.reason = "test"
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

    def test_get_run_find_correct_baseline_with_multiple_runs(self, client):
        language_1, language_2, name_1, name_2 = _uuid(), _uuid(), _uuid(), _uuid()
        contender_run_id, baseline_run_id_1, baseline_run_id_2 = (
            _uuid(),
            _uuid(),
            _uuid(),
        )

        self.authenticate(client)
        # Create contender run with two benchmark results
        _fixtures.benchmark_result(
            name=name_1,
            sha=_fixtures.CHILD,
            language=language_1,
            run_id=contender_run_id,
        )
        _fixtures.benchmark_result(
            name=name_2,
            sha=_fixtures.CHILD,
            language=language_1,
            run_id=contender_run_id,
        )
        # Create baseline run one benchmark result matching contender's
        _fixtures.benchmark_result(
            name=name_1,
            sha=_fixtures.PARENT,
            language=language_1,
            run_id=baseline_run_id_1,
        )
        # Create baseline run with no benchmark results matching contender's
        _fixtures.benchmark_result(
            name=name_1,
            sha=_fixtures.PARENT,
            language=language_2,
            run_id=baseline_run_id_2,
        )
        response = client.get(f"/api/runs/{contender_run_id}/")
        assert (
            response.json["links"]["baseline"]
            == f"http://localhost/api/runs/{baseline_run_id_1}/"
        )

    def test_get_run_without_baseline_run_with_matching_benchmarks(self, client):
        language_1, language_2, name, = (
            _uuid(),
            _uuid(),
            _uuid(),
        )
        contender_run_id, baseline_run_id = _uuid(), _uuid()

        self.authenticate(client)
        # Create contender run with one benchmark result
        _fixtures.benchmark_result(
            name=name, sha=_fixtures.CHILD, language=language_1, run_id=contender_run_id
        )
        # Create baseline run with no benchmark results matching contender's
        _fixtures.benchmark_result(
            name=name, sha=_fixtures.PARENT, language=language_2, run_id=baseline_run_id
        )
        response = client.get(f"/api/runs/{contender_run_id}/")
        assert not response.json["links"]["baseline"]

    def test_closest_commit_different_machines(self, client):
        # same benchmarks, different machines
        name, machine_1, machine_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        contender = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.PARENT,
            hardware_name=machine_2,
        )
        baseline = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.GRANDPARENT,
            hardware_name=machine_1,
        )
        _fixtures.benchmark_result(
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
        contender = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.PARENT,
            hardware_name=machine_2,
        )
        testing = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.GRANDPARENT,
            hardware_name=machine_1,
        )
        baseline = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.ELDER,
            hardware_name=machine_1,
        )

        testing_run = testing.run
        testing_run.name = "testing"
        testing_run.reason = "test"
        testing_run.save()

        contender_run = contender.run
        baseline_run = baseline.run

        response = client.get(f"/api/runs/{contender_run.id}/")
        self.assert_200_ok(response, _expected_entity(contender_run, baseline_run.id))


class TestRunList(_asserts.ListEnforcer):
    url = "/api/runs/"
    public = True

    def _create(self):
        _fixtures.benchmark_result(sha=_fixtures.PARENT)
        benchmark_result = _fixtures.benchmark_result()
        return benchmark_result.run

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

    def test_run_list_filter_by_multiple_sha(self, client):
        sha1 = _fixtures.CHILD
        sha2 = _fixtures.PARENT
        self.authenticate(client)
        _fixtures.benchmark_result(sha=_fixtures.PARENT)
        run_1 = _fixtures.benchmark_result()
        _fixtures.benchmark_result(sha=_fixtures.CHILD)
        run_2 = _fixtures.benchmark_result()
        response = client.get(f"/api/runs/?sha={sha1},{sha2}")

        self.assert_200_ok(
            response, contains=_expected_entity(run_1.run, include_baseline=False)
        )

        self.assert_200_ok(
            response, contains=_expected_entity(run_2.run, include_baseline=False)
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
        benchmark_result = _fixtures.benchmark_result()
        run_id = benchmark_result.run_id

        # can get before delete
        Run.one(id=run_id)

        # delete
        response = client.delete(f"/api/runs/{run_id}/")
        self.assert_204_no_content(response)

        # cannot get after delete
        with pytest.raises(NotFound):
            Run.one(id=run_id)


class TestRunPut(_asserts.PutEnforcer):
    url = "/api/runs/{}/"
    valid_payload = {
        "finished_timestamp": "2022-11-25 21:02:42.706806",
        "info": {"setup": "passed"},
        "error_info": {"error": "error", "stack_trace": "stack_trace", "fatal": True},
        "error_type": "fatal",
    }

    def setup(self):
        Run.delete_all()

    def _create_entity_to_update(self):
        _fixtures.benchmark_result(sha=_fixtures.PARENT)
        benchmark_result = _fixtures.benchmark_result()
        return benchmark_result.run

    def test_update_allowed_fields(self, client):
        self.authenticate(client)

        # before
        before = self._create_entity_to_update()
        for key in self.valid_payload.keys():
            assert getattr(before, key) is None

        # after
        response = client.put(f"/api/runs/{before.id}/", json=self.valid_payload)
        after = Run.one(id=before.id)
        self.assert_200_ok(response, _expected_entity(after))
        for key, value in self.valid_payload.items():
            if key == "finished_timestamp":
                assert str(getattr(after, key)) == value
            else:
                assert getattr(after, key) == value


class TestRunPost(_asserts.PostEnforcer):
    url = "/api/runs/"
    valid_payload = _fixtures.VALID_RUN_PAYLOAD
    valid_payload_for_cluster = _fixtures.VALID_RUN_PAYLOAD_FOR_CLUSTER
    valid_payload_with_error = _fixtures.VALID_RUN_PAYLOAD_WITH_ERROR
    required_fields = ["id"]

    # This test does not apply because we expect users to send run id when creating runs
    def test_cannot_set_id(self, client):
        pass

    def test_create_run(self, client):
        for hardware_type, payload in [
            ("machine", self.valid_payload),
            ("cluster", self.valid_payload_for_cluster),
        ]:
            self.authenticate(client)
            run_id = payload["id"]
            assert not Run.first(id=run_id)
            response = client.post(self.url, json=payload)
            print(response)
            print(response.json)
            run = Run.one(id=run_id)
            location = f"http://localhost/api/runs/{run_id}/"
            self.assert_201_created(response, _expected_entity(run), location)

            assert run.hardware.type == hardware_type
            for attr, value in payload[f"{hardware_type}_info"].items():
                assert getattr(run.hardware, attr) == value or getattr(
                    run.hardware, attr
                ) == int(value)

    def test_create_run_with_error(self, client):
        self.authenticate(client)
        run_id = self.valid_payload_with_error["id"]
        assert not Run.first(id=run_id)
        response = client.post(self.url, json=self.valid_payload_with_error)
        run = Run.one(id=run_id)
        location = f"http://localhost/api/runs/{run_id}/"
        self.assert_201_created(response, _expected_entity(run), location)
