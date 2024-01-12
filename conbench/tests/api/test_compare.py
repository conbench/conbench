from typing import List, Optional, Set, Tuple

import pytest

from ...api._examples import _api_compare_entity, _api_compare_list
from ...api.compare import CompareRunsAPI
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

CASE = "compression=snappy, cpu_count=2, dataset=nyctaxi_sample, file_type=parquet, input_type=arrow"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


class TestJoinResults:
    @staticmethod
    def _fake_benchmark_result(
        benchmark_result_id, case_id, context_id, has_commit=True
    ):
        """Just for this testing class, return a fake BenchmarkResult from which a
        case/context/hardware/repo/unit key can be extracted.

        This is easier than creating a real BenchmarkResult and all its dependencies...
        """
        hardware = FakeEntity("")
        hardware.hash = "hardware 1"
        commit = FakeEntity("")
        commit.repository = "repo 1"
        result = FakeEntity(benchmark_result_id)
        result.unit = "unit 1"
        result.case_id = case_id
        result.context_id = context_id
        result.hardware = hardware
        if has_commit:
            result.commit = commit
        else:
            result.commit = None
        result.history_fingerprint = case_id + context_id
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
            for _, baseline, contender in pairs
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

    def test_contender_missing_commit(self):
        baselines = [
            self._fake_benchmark_result("id1", "case 1", "context 1", has_commit=True),
            self._fake_benchmark_result("id2", "case 1", "context 2", has_commit=True),
            self._fake_benchmark_result("id3", "case 1", "context 3", has_commit=True),
        ]
        contenders = [
            self._fake_benchmark_result("id4", "case 1", "context 1", has_commit=False),
            self._fake_benchmark_result("id5", "case 1", "context 2", has_commit=False),
            self._fake_benchmark_result("id6", "case 1", "context 4", has_commit=False),
        ]
        pairs = CompareRunsAPI._join_results(baselines, contenders)
        assert self._parse_ids_from_pairs(pairs) == {
            ("id1", "id4"),
            ("id2", "id5"),
            ("id3", None),
            (None, "id6"),
        }


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
        result_dicts = [
            e.to_dict_for_json_api(include_joins=False) for e in new_entities
        ]
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
            history_fingerprint=new_entities[0].history_fingerprint,
            result_dicts=result_dicts,
        )
        expected["baseline"].update({"single_value_summary": 2.0})
        expected["contender"].update({"single_value_summary": 10.0})
        expected["analysis"]["pairwise"].update(
            {"percent_change": -400.0, "regression_indicated": True}
        )
        expected["analysis"]["lookback_z_score"].update(
            {
                "z_score": -26.16,
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
        result_dicts = [
            e.to_dict_for_json_api(include_joins=False) for e in new_entities
        ]
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
            history_fingerprint=new_entities[0].history_fingerprint,
            result_dicts=result_dicts,
        )

        expected["baseline"].update({"single_value_summary": None, "error": error})
        expected["contender"].update({"single_value_summary": 10.0})
        expected["analysis"]["pairwise"] = None
        expected["analysis"]["lookback_z_score"] = None
        expected["unit"] = None
        expected["less_is_better"] = None

        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/benchmark-results/foo...bar/")
        self.assert_404_not_found(response)

    @pytest.mark.parametrize(
        ["baseline_result_id", "expected_z_score"],
        [
            # result on the fork point commit
            (5, -2.358),
            # result on the parent commit
            (6, -3.023),
            # result on the head commit of the default branch
            (8, 0.0459),
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
        fingerprints = [e.history_fingerprint for e in new_entities]
        result_dicts = [
            e.to_dict_for_json_api(include_joins=False) for e in new_entities
        ]
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
            history_fingerprints=fingerprints,
            result_dicts=result_dicts,
        )
        for e in expected:
            e["analysis"]["lookback_z_score"] = None

        self.assert_200_ok(
            response,
            {
                "data": sorted(expected, key=lambda e: e["history_fingerprint"]),
                "metadata": {"next_page_cursor": None},
            },
        )

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
        fingerprints = [e.history_fingerprint for e in new_entities]
        result_dicts = [
            e.to_dict_for_json_api(include_joins=False) for e in new_entities
        ]
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
            history_fingerprints=fingerprints,
            result_dicts=result_dicts,
        )
        expected[0]["analysis"]["lookback_z_score"] = None
        expected[1]["unit"] = None
        expected[1]["less_is_better"] = None
        expected[1]["baseline"].update({"single_value_summary": None, "error": error})
        expected[1]["contender"].update({"single_value_summary": None, "error": error})
        expected[1]["analysis"]["pairwise"] = None
        expected[1]["analysis"]["lookback_z_score"] = None

        self.assert_200_ok(
            response,
            {
                "data": sorted(expected, key=lambda e: e["history_fingerprint"]),
                "metadata": {"next_page_cursor": None},
            },
        )

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/runs/foo...bar/")
        self.assert_404_not_found(response)

    @pytest.mark.parametrize("page_size", ["0", "1001", "-1", "asd"])
    def test_bad_page_size(self, client, page_size):
        self.authenticate(client)
        res = client.get(f"/api/compare/runs/foo...bar/?page_size={page_size}")
        self.assert_400_bad_request(
            res,
            {"_errors": ["page_size must be a positive integer no greater than 1000"]},
        )

    @pytest.mark.parametrize(
        ["baseline_result_id", "expected_z_score"],
        [
            # result on the fork point commit
            (5, -2.358),
            # result on the parent commit
            (6, -3.023),
            # result on the head commit of the default branch
            (8, 0.0459),
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
            response.json["data"][0]["analysis"]["lookback_z_score"]["z_score"]
            == expected_z_score
        )

    def test_pagination(self, client):
        self.authenticate(client)

        # Retry the 'c' benchmark on purpose. Due to the full outer join we should
        # expect to see 4 comparisons for 'c', all on the same page.
        names = ["a", "b", "c", "c"]
        names_by_fingerprint = {}
        for run_id in ["baseline", "contender"]:
            for name in names:
                result = _fixtures.benchmark_result(run_id=run_id, name=name)
                names_by_fingerprint[result.history_fingerprint] = name

        # Fingerprints are randomly generated, so the order will change with each run of
        # this test.
        expected_first_page_names = []
        expected_second_page_names = []
        for ix, fingerprint in enumerate(sorted(names_by_fingerprint.keys())):
            name = names_by_fingerprint[fingerprint]
            page = expected_first_page_names if ix < 2 else expected_second_page_names
            if name == "c":
                page += ["c"] * 4
            else:
                page.append(name)

        print(f"{expected_first_page_names=}\n{expected_second_page_names=}")
        url = "/api/compare/runs/baseline...contender/?page_size=2"

        res = client.get(url)
        self.assert_200_ok(res)
        assert [
            r["baseline"]["benchmark_name"] for r in res.json["data"]
        ] == expected_first_page_names
        cursor = res.json["metadata"]["next_page_cursor"]
        assert cursor

        res = client.get(f"{url}&cursor={cursor}")
        self.assert_200_ok(res)
        assert [
            r["baseline"]["benchmark_name"] for r in res.json["data"]
        ] == expected_second_page_names
        assert res.json["metadata"]["next_page_cursor"] is None

        # Try to go past the end of the list.
        res = client.get(f"{url}&cursor=zzz")
        self.assert_200_ok(res, {"data": [], "metadata": {"next_page_cursor": None}})
