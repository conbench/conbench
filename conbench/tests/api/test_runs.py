from datetime import datetime, timezone

from conbench.util import tznaive_dt_to_aware_iso8601_for_api

from ...api._examples import _api_run_entity
from ...entities.benchmark_result import BenchmarkResult
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

DEFAULT_BRANCH_PLACEHOLDER = {
    "error": "the contender run is already on the default branch",
    "baseline_run_id": None,
    "commits_skipped": None,
}


def _expected_entity(result: BenchmarkResult, candidate_baseline_runs=None):
    parent = result.commit.get_parent_commit() if result.commit else None
    entity = _api_run_entity(
        result.run_id,
        result.run_tags,
        result.run_reason,
        result.commit_id,
        parent.id if parent else None,
        result.hardware_id,
        result.hardware.name,
        result.hardware.type,
        tznaive_dt_to_aware_iso8601_for_api(result.timestamp),
    )
    if candidate_baseline_runs:
        entity["candidate_baseline_runs"] = candidate_baseline_runs
    else:
        del entity["candidate_baseline_runs"]
    return entity


class TestRunGet(_asserts.GetEnforcer):
    url = "/api/runs/{}/"
    public = True

    def _create_results(self, name=None, language=None):
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
        return contender, baseline

    def test_unauthenticated(self, client, monkeypatch):
        """Override the parent class method since there is no official Run entity."""
        result = _fixtures.benchmark_result()
        entity_url = self.url.format(result.run_id)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        response = client.get(entity_url)
        self.assert_401_unauthorized(response)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
        response = client.get(entity_url)
        self.assert_200_ok(response)

    def test_get_run(self, client):
        # change anything about the context so we get only one baseline
        language, name = _uuid(), _uuid()

        self.authenticate(client)
        result, baseline = self._create_results(name=name, language=language)
        response = client.get(f"/api/runs/{result.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                result,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [result.commit.sha],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [],
                        "error": None,
                    },
                },
            ),
        )

    def test_get_run_without_commit(self, client):
        self.authenticate(client)
        result = _fixtures.benchmark_result(no_github=True)
        response = client.get(f"/api/runs/{result.run_id}/")
        expected = _expected_entity(
            result,
            candidate_baseline_runs={
                "fork_point": {
                    "baseline_run_id": None,
                    "commits_skipped": None,
                    "error": "the contender run is not connected to the git graph",
                },
                "latest_default": {
                    "baseline_run_id": None,
                    "commits_skipped": None,
                    "error": "this baseline commit type does not exist for this run",
                },
                "parent": {
                    "baseline_run_id": None,
                    "commits_skipped": None,
                    "error": "the contender run is not connected to the git graph",
                },
            },
        )
        expected["commit"] = None
        self.assert_200_ok(response, expected)

    def test_get_run_should_not_prefer_test_runs_as_baseline(self, client):
        """Test runs shouldn't be preferred, but if they are the only runs that exist,
        we'll pick them up"""
        # change anything about the context so we get only one baseline
        language, name = _uuid(), _uuid()

        self.authenticate(client)
        result, baseline = self._create_results(name=name, language=language)
        baseline.run_reason = "test"
        baseline.save()
        response = client.get(f"/api/runs/{result.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                result,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [result.commit.sha],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [],
                        "error": None,
                    },
                },
            ),
        )

    def test_get_run_find_correct_baseline_many_matching_contexts(self, client):
        # same context for different benchmark runs, but different benchmarks
        language, name_1, name_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        result_1, baseline_1 = self._create_results(name=name_1, language=language)
        result_2, baseline_2 = self._create_results(name=name_2, language=language)
        response = client.get(f"/api/runs/{result_1.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                result_1,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline_1.run_id,
                        "commits_skipped": [result_1.commit.sha],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline_1.run_id,
                        "commits_skipped": [],
                        "error": None,
                    },
                },
            ),
        )
        response = client.get(f"/api/runs/{result_2.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                result_2,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline_2.run_id,
                        "commits_skipped": [result_2.commit.sha],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline_2.run_id,
                        "commits_skipped": [],
                        "error": None,
                    },
                },
            ),
        )

    def test_get_run_find_correct_baseline_with_multiple_runs(self, client):
        language_1, language_2, name_1, name_2 = _uuid(), _uuid(), _uuid(), _uuid()
        contender_run_id, baseline_run_id_1, baseline_run_id_2 = (
            _uuid(),
            _uuid(),
            _uuid(),
        )

        self.authenticate(client)
        # Create contender run with two benchmark results
        a_contender_result = _fixtures.benchmark_result(
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
        assert response.json["candidate_baseline_runs"] == {
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "baseline_run_id": baseline_run_id_1,
                "commits_skipped": [a_contender_result.commit.sha],
                "error": None,
            },
            "parent": {
                "baseline_run_id": baseline_run_id_1,
                "commits_skipped": [],
                "error": None,
            },
        }

    def test_get_run_without_baseline_run_with_matching_benchmarks(self, client):
        (
            language_1,
            language_2,
            name,
        ) = (
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
        assert response.json["candidate_baseline_runs"] == {
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "baseline_run_id": None,
                "commits_skipped": None,
                "error": "no matching baseline run was found",
            },
            "parent": {
                "baseline_run_id": None,
                "commits_skipped": None,
                "error": "no matching baseline run was found",
            },
        }

    def test_closest_commit_different_machines(self, client):
        # same benchmarks, different machines
        name, machine_1, machine_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        contender = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        parent = _fixtures.benchmark_result(
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

        response = client.get(f"/api/runs/{contender.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                contender,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [
                            contender.commit.sha,
                            parent.commit.sha,
                        ],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [parent.commit.sha],
                        "error": None,
                    },
                },
            ),
        )

    def test_closest_commit_different_machines_should_not_prefer_test_runs_as_baseline(
        self, client
    ):
        """Test runs shouldn't be preferred, but if they are the only runs that exist,
        we'll pick them up"""
        # same benchmarks, different machines, skip test run
        name, machine_1, machine_2 = _uuid(), _uuid(), _uuid()

        self.authenticate(client)
        contender = _fixtures.benchmark_result(
            name=name,
            sha=_fixtures.CHILD,
            hardware_name=machine_1,
        )
        parent = _fixtures.benchmark_result(
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

        testing.run_reason = "test"
        testing.save()

        response = client.get(f"/api/runs/{contender.run_id}/")
        self.assert_200_ok(
            response,
            _expected_entity(
                contender,
                candidate_baseline_runs={
                    "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
                    "latest_default": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [
                            contender.commit.sha,
                            parent.commit.sha,
                            testing.commit.sha,
                        ],
                        "error": None,
                    },
                    "parent": {
                        "baseline_run_id": baseline.run_id,
                        "commits_skipped": [
                            parent.commit.sha,
                            testing.commit.sha,
                        ],
                        "error": None,
                    },
                },
            ),
        )


class TestRunList(_asserts.ListEnforcer):
    url = "/api/runs/"
    public = True

    def _create(self):
        # In this test class it's important to supply a timestamp of now() when creating
        # BenchmarkResults because the list runs endpoint looks at the last 30 days of
        # BenchmarkResults.
        _fixtures.benchmark_result(
            sha=_fixtures.PARENT, timestamp=datetime.now(timezone.utc).isoformat()
        )
        benchmark_result = _fixtures.benchmark_result(
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        return benchmark_result

    def test_run_list(self, client):
        self.authenticate(client)
        result = self._create()
        response = client.get("/api/runs/")
        self.assert_200_ok(response, contains=_expected_entity(result))

    def test_run_list_filter_by_sha(self, client):
        sha = _fixtures.CHILD
        self.authenticate(client)
        result = self._create()
        response = client.get(f"/api/runs/?sha={sha}")
        self.assert_200_ok(response, contains=_expected_entity(result))

    def test_run_list_filter_by_multiple_sha(self, client):
        sha1 = _fixtures.CHILD
        sha2 = _fixtures.PARENT
        self.authenticate(client)
        _fixtures.benchmark_result(
            sha=_fixtures.PARENT, timestamp=datetime.now(timezone.utc).isoformat()
        )
        result_1 = _fixtures.benchmark_result(
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        _fixtures.benchmark_result(
            sha=_fixtures.CHILD, timestamp=datetime.now(timezone.utc).isoformat()
        )
        result_2 = _fixtures.benchmark_result(
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        response = client.get(f"/api/runs/?sha={sha1},{sha2}")

        self.assert_200_ok(response, contains=_expected_entity(result_1))

        self.assert_200_ok(response, contains=_expected_entity(result_2))

    def test_run_list_filter_by_sha_no_match(self, client):
        sha = "some unknown sha"
        self.authenticate(client)
        self._create()
        response = client.get(f"/api/runs/?sha={sha}")
        self.assert_200_ok(response, [])


class TestRunDelete(_asserts.ApiEndpointTest):
    """Deprecated at this time; always returns a 204"""

    url = "api/runs/{}/"

    def test_delete_run(self, client):
        self.authenticate(client)
        benchmark_result = _fixtures.benchmark_result()
        run_id = benchmark_result.run_id

        # can get before delete
        BenchmarkResult.one(run_id=run_id)

        # delete
        response = client.delete(f"/api/runs/{run_id}/")
        self.assert_204_no_content(response)

        # can still get after delete
        BenchmarkResult.one(run_id=run_id)


class TestRunPut(_asserts.ApiEndpointTest):
    """Deprecated at this time; always returns a 200"""

    url = "/api/runs/{}/"
    valid_payload = {
        "finished_timestamp": "2022-11-25T21:02:45Z",
        "info": {"setup": "passed"},
        "error_info": {"error": "error", "stack_trace": "stack_trace", "fatal": True},
        "error_type": "fatal",
    }

    def test_put_run(self, client):
        self.authenticate(client)

        # before
        result_before = _fixtures.benchmark_result()

        # mutate run in db (no-op)
        resp = client.put(f"/api/runs/{result_before.run_id}/", json=self.valid_payload)
        assert resp.status_code == 200, resp.status_code

        # receive not-mutated run from db
        resp = client.get(f"/api/runs/{result_before.run_id}/")
        assert resp.status_code == 200, resp.status_code


class TestRunPost(_asserts.ApiEndpointTest):
    """Deprecated at this time; always returns a 201"""

    url = "/api/runs/"

    def test_create_run(self, client):
        self.authenticate(client)
        payload = _fixtures.VALID_RUN_PAYLOAD
        run_id = payload["id"]
        assert not BenchmarkResult.first(run_id=run_id)
        response = client.post(self.url, json=payload)
        assert response.status_code == 201
        assert response.json == {}
