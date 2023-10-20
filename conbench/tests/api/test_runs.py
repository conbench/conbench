import logging
from datetime import datetime, timedelta

import pytest

from conbench.util import tznaive_dt_to_aware_iso8601_for_api

from ...api._examples import _api_run_entity
from ...api.runs import get_candidate_baseline_runs
from ...entities.benchmark_result import BenchmarkResult
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

DEFAULT_BRANCH_PLACEHOLDER = {
    "error": "the contender run is already on the default branch",
    "baseline_run_id": None,
    "commits_skipped": None,
}

log = logging.getLogger(__name__)


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
        result = _fixtures.benchmark_result(repo_without_commit=_fixtures.REPO)
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
    url = "/api/runs/?commit_hash=abc"
    public = True

    def _create(self):
        _fixtures.benchmark_result(sha=_fixtures.PARENT)
        benchmark_result = _fixtures.benchmark_result()
        return benchmark_result

    def test_run_list_filter_by_commit_hash(self, client):
        commit_hash = _fixtures.CHILD
        self.authenticate(client)
        result = _fixtures.benchmark_result()
        response = client.get(f"/api/runs/?commit_hash={commit_hash}")
        self.assert_200_ok(response)
        assert _expected_entity(result) in response.json["data"]

    def test_run_list_filter_by_multiple_commits(self, client):
        hash1 = _fixtures.CHILD
        hash2 = _fixtures.PARENT
        self.authenticate(client)
        _fixtures.benchmark_result(sha=_fixtures.PARENT)
        result_1 = _fixtures.benchmark_result()
        _fixtures.benchmark_result(sha=_fixtures.CHILD)
        result_2 = _fixtures.benchmark_result()
        response = client.get(f"/api/runs/?commit_hash={hash1},{hash2}")
        assert _expected_entity(result_1) in response.json["data"]
        assert _expected_entity(result_2) in response.json["data"]

    def test_run_list_filter_by_commit_hash_no_match(self, client):
        commit_hash = "some unknown commit_hash"
        self.authenticate(client)
        self._create()
        response = client.get(f"/api/runs/?commit_hash={commit_hash}")
        self.assert_200_ok(
            response, {"data": [], "metadata": {"next_page_cursor": None}}
        )

    def test_run_list_no_commit_hash(self, client):
        self.authenticate(client)
        response = client.get("/api/runs/")
        self.assert_400_bad_request(response, {"_errors": ["commit_hash is required"]})

    @pytest.mark.parametrize("page_size", ["0", "1001", "-1", "asd"])
    def test_bad_page_size(self, client, page_size):
        self.authenticate(client)
        res = client.get(f"{self.url}&page_size={page_size}")
        self.assert_400_bad_request(
            res,
            {"_errors": ["page_size must be a positive integer no greater than 1000"]},
        )

    def test_pagination(self, client):
        self.authenticate(client)
        timestamp = datetime(2023, 10, 1)
        for run_id in ["1", "2", "3"]:
            for _ in range(2):
                _fixtures.benchmark_result(
                    run_id=run_id, sha="abc", timestamp=timestamp.isoformat()
                )
                timestamp += timedelta(days=1)

        res = client.get(f"{self.url}&page_size=2")
        self.assert_200_ok(res)
        assert len(res.json["data"]) == 2
        assert {r["id"] for r in res.json["data"]} == {"1", "2"}
        cursor = res.json["metadata"]["next_page_cursor"]
        assert cursor

        res = client.get(f"{self.url}&page_size=2&cursor={cursor}")
        self.assert_200_ok(res)
        assert len(res.json["data"]) == 1
        assert {r["id"] for r in res.json["data"]} == {"3"}
        assert res.json["metadata"]["next_page_cursor"] is None


def test_get_candidate_baseline_runs():
    commits, benchmark_results = _fixtures.gen_fake_data()
    run_ids = [result.run_id for result in benchmark_results]
    # Corresponding to these fake runs:
    expected_baseline_run_dicts = [
        # run 0, commit 11111
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 1, commit 22222
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[0],
                "commits_skipped": [],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 2, commit aaaaa
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 3, commit bbbbb
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[2],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 4, commit ddddd
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["ccccc", "33333"],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["33333"],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 5, commit 44444
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["33333"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 6, commit fffff
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["eeeee"],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 7, commit 00000
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[6],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 8, commit 66666
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 9, commit 66666
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[8],
                "commits_skipped": [],
            },
        },
        # run 10, commit abcde (different repo)
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 11, commit 'sha' (no detailed commit info)
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "latest_default": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 12, commit 66666 (different case)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 13, commit 66666 (different context)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 14, commit 66666 (different hardware)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 15, commit 66666 (nightly reason)
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
    ]
    assert len(run_ids) == len(expected_baseline_run_dicts), "you should test all runs"
    log.info(list(enumerate(run_ids)))

    failures = []
    for ix, (result, expected_baseline_run_dict) in enumerate(
        zip(benchmark_results, expected_baseline_run_dicts)
    ):
        actual_baseline_run_dict = get_candidate_baseline_runs(result)
        if actual_baseline_run_dict != expected_baseline_run_dict:
            failures.append(ix)
            log.info(
                "run %d: expected:\n%s, but got \n%s",
                ix,
                expected_baseline_run_dict,
                actual_baseline_run_dict,
            )
    assert not failures

    # create one more nightly on 44444 and hope that we pick it up in the last test case
    # (which should also have a nightly reason)
    new_benchmark_result = _fixtures.benchmark_result(
        name=benchmark_results[-1].case.name,
        results=[1, 2, 3],
        reason="nightly",
        commit=commits["44444"],
    )
    actual_baseline_run_dict = get_candidate_baseline_runs(benchmark_results[-1])
    assert actual_baseline_run_dict == {
        "parent": {
            "error": None,
            "baseline_run_id": new_benchmark_result.run_id,
            "commits_skipped": ["55555"],
        },
        "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
        "latest_default": {
            "error": None,
            "baseline_run_id": new_benchmark_result.run_id,
            "commits_skipped": ["66666", "55555"],
        },
    }

    # test a run with no commit that can still find a latest_default baseline
    benchmark_result_missing_commit = _fixtures.benchmark_result(
        name=benchmark_results[1].case.name,
        results=[1, 2, 3],
        repo_without_commit=_fixtures.REPO,
    )
    assert benchmark_result_missing_commit.commit is None
    actual_baseline_run_dict = get_candidate_baseline_runs(
        benchmark_result_missing_commit
    )
    assert actual_baseline_run_dict == {
        "parent": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "fork_point": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "latest_default": {
            "error": None,
            "baseline_run_id": run_ids[9],  # latest with same reason (commit)
            "commits_skipped": [],
        },
    }

    # test a run with no commit that cannot find a latest_default baseline because there
    # are no commits on its repo's default branch
    benchmark_result_different_repo = _fixtures.benchmark_result(
        name=benchmark_results[1].case.name,
        results=[1, 2, 3],
        repo_without_commit="https://github.com/org/doesnt_exist",
    )
    assert benchmark_result_different_repo.commit is None
    actual_baseline_run_dict = get_candidate_baseline_runs(
        benchmark_result_different_repo
    )
    assert actual_baseline_run_dict == {
        "parent": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "fork_point": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "latest_default": {
            "error": "this baseline commit type does not exist for this run",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
    }
