from typing import List, Optional, Set, Tuple

import pytest

from ...api._examples import _api_compare_entity, _api_compare_list
from ...api.compare import CompareRunsAPI, _round
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

CASE = "compression=snappy, cpu_count=2, dataset=nyctaxi_sample, file_type=parquet, input_type=arrow"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


class TestJoinResults:
    @staticmethod
    def _fake_benchmark_result(benchmark_result_id, case_id, context_id):
        """Just for this testing class, return a fake BenchmarkResult from which a
        case/context/hardware/repo/unit key can be extracted.

        This is easier than creating a real BenchmarkResult and all its dependencies...
        """
        hardware = FakeEntity("")
        hardware.hash = "hardware 1"
        commit = FakeEntity("")
        commit.repository = "repo 1"
        run = FakeEntity("")
        run.hardware = hardware
        run.commit = commit

        result = FakeEntity(benchmark_result_id)
        result.unit = "unit 1"
        result.case_id = case_id
        result.context_id = context_id
        result.run = run
        return result

    @staticmethod
    def _parse_ids_from_pairs(
        pairs: List[Tuple[Optional[FakeEntity], Optional[FakeEntity]]]
    ) -> Set[Tuple[Optional[str], Optional[str]]]:
        """Parse each pair returned from CompareRunsAPI._join_results() into a tuple of
        the results' IDs, for easier comparison. Return a set of these tuples.
        """
        return {
            (
                baseline.id if baseline is not None else None,
                contender.id if contender is not None else None,
            )
            for baseline, contender in pairs
        }

    def test_empty(self):
        assert CompareRunsAPI._join_results([], []) == []

    def test_baseline_empty(self):
        baselines = []
        contenders = [self._fake_benchmark_result("id1", "case 1", "context 1")]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {(None, "id1")}

    def test_contender_empty(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 2", "context 2"),
            self._fake_benchmark_result("id3", "case 2", "context 2"),
        ]
        contenders = []
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {
            ("id1", None),
            ("id2", None),
            ("id3", None),
        }

    def test_mismatch(self):
        baselines = [self._fake_benchmark_result("id1", "case 1", "context 1")]
        contenders = [self._fake_benchmark_result("id2", "case 2", "context 2")]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {("id1", None), (None, "id2")}

    def test_simple_match(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 2", "context 2"),
        ]
        contenders = [
            self._fake_benchmark_result("id3", "case 1", "context 1"),
            self._fake_benchmark_result("id4", "case 2", "context 2"),
        ]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {("id1", "id3"), ("id2", "id4")}

    def test_duplicates_cause_cartesian_product(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 2", "context 2"),
            self._fake_benchmark_result("id3", "case 2", "context 2"),
            self._fake_benchmark_result("id4", "case 3", "context 3"),
            self._fake_benchmark_result("id5", "case 3", "context 3"),
        ]
        contenders = [
            self._fake_benchmark_result("id6", "case 1", "context 1"),
            self._fake_benchmark_result("id7", "case 1", "context 1"),
            self._fake_benchmark_result("id8", "case 2", "context 2"),
            self._fake_benchmark_result("id9", "case 3", "context 3"),
            self._fake_benchmark_result("id0", "case 3", "context 3"),
            self._fake_benchmark_result("id00", "case 4", "context 4"),
        ]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {
            ("id1", "id6"),
            ("id1", "id7"),
            ("id2", "id8"),
            ("id3", "id8"),
            ("id4", "id9"),
            ("id4", "id0"),
            ("id5", "id9"),
            ("id5", "id0"),
            (None, "id00"),
        }

    def test_contexts_dont_match_so_dont_pair(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 2", "context 2"),
        ]
        contenders = [
            self._fake_benchmark_result("id3", "case 1", "context 3"),
            self._fake_benchmark_result("id4", "case 2", "context 4"),
        ]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {
            ("id1", None),
            ("id2", None),
            (None, "id3"),
            (None, "id4"),
        }

    def test_multiple_contexts_for_same_cases_but_they_line_up(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 1", "context 2"),
        ]
        contenders = [
            self._fake_benchmark_result("id3", "case 1", "context 1"),
            self._fake_benchmark_result("id4", "case 1", "context 2"),
        ]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {("id1", "id3"), ("id2", "id4")}

    def test_multiple_contexts_for_same_cases_but_they_kinda_line_up(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1"),
            self._fake_benchmark_result("id2", "case 1", "context 2"),
        ]
        contenders = [self._fake_benchmark_result("id3", "case 1", "context 1")]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {("id1", "id3"), ("id2", None)}


class TestCompareBenchmarkResultsGet(_asserts.GetEnforcer):
    url = "/api/compare/benchmark-results/{}/"
    public = True

    def _create(self, name=None, verbose=False):
        # create a distribution history & a regression
        _fixtures.benchmark_result(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            sha=_fixtures.GRANDPARENT,
        )
        benchmark_result_1 = _fixtures.benchmark_result(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            sha=_fixtures.PARENT,
        )
        benchmark_result_2 = _fixtures.benchmark_result(
            name=name,
            results=_fixtures.RESULTS_UP[2],
        )

        entity = FakeEntity(f"{benchmark_result_1.id}...{benchmark_result_2.id}")
        if verbose:
            return [benchmark_result_1, benchmark_result_2], entity
        return entity

    def _create_with_error(self, name=None, baseline_error=None, verbose=False):
        # create a distribution history & a regression
        _fixtures.benchmark_result(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            sha=_fixtures.GRANDPARENT,
        )
        benchmark_result_1 = _fixtures.benchmark_result(
            name=name,
            results=None,
            sha=_fixtures.PARENT,
            error=baseline_error,
            empty_results=True,
        )
        benchmark_result_2 = _fixtures.benchmark_result(
            name=name,
            results=_fixtures.RESULTS_UP[2],
        )

        entity = FakeEntity(f"{benchmark_result_1.id}...{benchmark_result_2.id}")
        if verbose:
            return [benchmark_result_1, benchmark_result_2], entity
        return entity

    @pytest.mark.parametrize("threshold_z", [None, "5.7"])
    def test_compare(self, client, threshold_z):
        self.authenticate(client)
        name = _uuid()
        new_entities, compare = self._create(name, verbose=True)
        query_string = {"threshold_z": threshold_z} if threshold_z else None
        response = client.get(
            f"/api/compare/benchmark-results/{compare.id}/", query_string=query_string
        )

        benchmark_result_ids = [e.id for e in new_entities]
        batch_ids = [e.batch_id for e in new_entities]
        run_ids = [e.run_id for e in new_entities]
        expected = _api_compare_entity(
            benchmark_result_ids,
            batch_ids,
            run_ids,
            name,
            CASE,
            tags={
                "dataset": "nyctaxi_sample",
                "cpu_count": "2",
                "file_type": "parquet",
                "input_type": "arrow",
                "compression": "snappy",
                # The benchmark name should in the future not be part of the
                # emitted tags anymore.
                "name": name,
            },
        )
        expected["baseline"].update({"single_value_summary": 3.0})
        expected["contender"].update({"single_value_summary": 20.0})
        expected["analysis"]["pairwise"].update(
            {"percent_change": -566.7, "regression_indicated": True}
        )
        expected["analysis"]["lookback_z_score"].update(
            {
                "z_score": _round(-_fixtures.Z_SCORE_UP),
                "regression_indicated": True,
            }
        )
        if threshold_z:
            expected["analysis"]["lookback_z_score"]["z_threshold"] = float(threshold_z)
        self.assert_200_ok(response, expected)

    def test_compare_with_error(self, client):
        self.authenticate(client)
        name = _uuid()
        error = {"stack trace": "stack trace"}
        new_entities, compare = self._create_with_error(
            name, baseline_error=error, verbose=True
        )
        response = client.get(f"/api/compare/benchmark-results/{compare.id}/")

        benchmark_result_ids = [e.id for e in new_entities]
        batch_ids = [e.batch_id for e in new_entities]
        run_ids = [e.run_id for e in new_entities]
        expected = _api_compare_entity(
            benchmark_result_ids,
            batch_ids,
            run_ids,
            name,
            CASE,
            tags={
                "dataset": "nyctaxi_sample",
                "cpu_count": "2",
                "file_type": "parquet",
                "input_type": "arrow",
                "compression": "snappy",
                "name": name,
            },
        )

        expected["baseline"].update({"single_value_summary": None, "error": error})
        expected["contender"].update({"single_value_summary": 20.0})
        expected["analysis"]["pairwise"] = None
        expected["analysis"]["lookback_z_score"] = None

        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/benchmark-results/foo...bar/")
        self.assert_404_not_found(response)

    @pytest.mark.parametrize(
        ["baseline_result_id", "expected_z_score"],
        [
            # result on the fork point commit
            (5, -2.186),
            # result on the parent commit
            (6, -2.825),
            # result on the head commit of the default branch
            (8, 0.1205),
        ],
    )
    def test_compare_different_baselines(
        self, client, baseline_result_id, expected_z_score
    ):
        self.authenticate(client)
        _, benchmark_results = _fixtures.gen_fake_data()
        contender_result = benchmark_results[7]  # on a PR branch
        baseline_result = benchmark_results[baseline_result_id]
        response = client.get(
            f"/api/compare/benchmark-results/{baseline_result.id}...{contender_result.id}/"
        )
        assert response.status_code == 200, response.status_code
        assert (
            response.json["analysis"]["lookback_z_score"]["z_score"] == expected_z_score
        )


class TestCompareRunsGet(_asserts.GetEnforcer):
    url = "/api/compare/runs/{}/"
    public = True

    def _create(self, verbose=False, run_id=None, batch_id=None):
        run_id = run_id if run_id is not None else _uuid()
        benchmark_result_1 = _fixtures.benchmark_result(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        benchmark_result_2 = _fixtures.benchmark_result(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
        )
        entity = FakeEntity(f"{run_id}...{run_id}")
        if verbose:
            return [benchmark_result_1, benchmark_result_2], entity
        return entity

    def _create_with_error(
        self, verbose=False, run_id=None, batch_id=None, baseline_error=None
    ):
        run_id = run_id if run_id is not None else _uuid()
        benchmark_result_1 = _fixtures.benchmark_result(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        benchmark_result_2 = _fixtures.benchmark_result(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
            results=None,
            error=baseline_error,
            empty_results=True,
        )
        entity = FakeEntity(f"{run_id}...{run_id}")
        if verbose:
            return [benchmark_result_1, benchmark_result_2], entity
        return entity

    @pytest.mark.parametrize("threshold_z", [None, "5.7"])
    def test_compare(self, client, threshold_z):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        new_entities, compare = self._create(
            verbose=True,
            run_id=run_id,
            batch_id=batch_id,
        )
        new_ids = [e.id for e in new_entities]
        query_string = {"threshold_z": threshold_z} if threshold_z else None
        response = client.get(
            f"/api/compare/runs/{compare.id}/", query_string=query_string
        )

        # cheating by comparing run to same run
        run_ids = [run_id, run_id]
        batch_ids = [batch_id, batch_id]
        batches = ["read", "write"]
        benchmarks = [CASE, CASE]
        expected = _api_compare_list(
            new_ids,
            new_ids,
            batch_ids,
            run_ids,
            batches,
            benchmarks,
            tags=[
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": "2",
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "read",
                },
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": "2",
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "write",
                },
            ],
        )
        for e in expected:
            e["analysis"]["lookback_z_score"] = None

        self.assert_200_ok(response, None, contains=expected[0])
        self.assert_200_ok(response, None, contains=expected[1])

    def test_compare_with_error(self, client):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        error = {"stack trace": "stack trace"}
        new_entities, compare = self._create_with_error(
            verbose=True,
            run_id=run_id,
            batch_id=batch_id,
            baseline_error=error,
        )
        new_ids = [e.id for e in new_entities]
        response = client.get(f"/api/compare/runs/{compare.id}/")

        # cheating by comparing run to same run
        run_ids = [run_id, run_id]
        batch_ids = [batch_id, batch_id]
        batches = ["read", "write"]
        benchmarks = [CASE, CASE]
        expected = _api_compare_list(
            new_ids,
            new_ids,
            batch_ids,
            run_ids,
            batches,
            benchmarks,
            tags=[
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": "2",
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "read",
                },
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": "2",
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "write",
                },
            ],
        )
        expected[0]["analysis"]["lookback_z_score"] = None
        expected[1]["unit"] = "unknown"
        expected[1]["baseline"].update({"single_value_summary": None, "error": error})
        expected[1]["contender"].update({"single_value_summary": None, "error": error})
        expected[1]["analysis"]["pairwise"] = None
        expected[1]["analysis"]["lookback_z_score"] = None
        self.assert_200_ok(response, None, contains=expected[0])
        self.assert_200_ok(response, None, contains=expected[1])

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/runs/foo...bar/")
        self.assert_404_not_found(response)

    @pytest.mark.parametrize(
        ["baseline_result_id", "expected_z_score"],
        [
            # result on the fork point commit
            (5, -2.186),
            # result on the parent commit
            (6, -2.825),
            # result on the head commit of the default branch
            (8, 0.1205),
        ],
    )
    def test_compare_different_baselines(
        self, client, baseline_result_id, expected_z_score
    ):
        self.authenticate(client)
        _, benchmark_results = _fixtures.gen_fake_data()
        contender_run_id = benchmark_results[7].run_id  # on a PR branch
        baseline_run_id = benchmark_results[baseline_result_id].run_id
        response = client.get(
            f"/api/compare/runs/{baseline_run_id}...{contender_run_id}/"
        )
        assert response.status_code == 200, response.status_code
        assert (
            response.json[0]["analysis"]["lookback_z_score"]["z_score"]
            == expected_z_score
        )
