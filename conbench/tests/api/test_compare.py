from ...api._examples import (
    _api_compare_entity,
    _api_compare_list,
    _api_compare_summary,
)
from ...api.compare import _get_pairs
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

CASE = "snappy, cpu_count=2, parquet, arrow, nyctaxi_sample"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


def _fake_compare_entity(summary_id, case_id, context_id):
    return {
        "id": summary_id,
        "batch_id": "some_batch_id",
        "run_id": "some_run_id",
        "case_id": case_id,
        "context_id": context_id,
        "value": "some_value",
        "unit": "some_unit",
        "benchmark": "some_benchmark",
        "batch": "some_batch",
        "language": "some_language",
        "tags": "some_tags",
        "z_score": "some_zscore",
    }


class TestGetPairs:
    def test_empty(self):
        assert _get_pairs([], []) == {}

    def test_mismatch(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
        ]
        contenders = [
            _fake_compare_entity("id2", "case 2", "context 2"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == ["case 1-context 1", "case 2-context 2"]
        assert pairs["case 1-context 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1-context 1"]["contender"] is None
        assert pairs["case 2-context 2"]["baseline"] is None
        assert pairs["case 2-context 2"]["contender"]["id"] == "id2"

    def test_simple_match(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 2", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id3", "case 1", "context 1"),
            _fake_compare_entity("id4", "case 2", "context 2"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == ["case 1", "case 2"]
        assert pairs["case 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1"]["contender"]["id"] == "id3"
        assert pairs["case 2"]["baseline"]["id"] == "id2"
        assert pairs["case 2"]["contender"]["id"] == "id4"

    def test_duplicates_get_skipped(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 2", "context 2"),  # duplicate
            _fake_compare_entity("id3", "case 2", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id4", "case 1", "context 1"),  # duplicate
            _fake_compare_entity("id5", "case 1", "context 1"),
            _fake_compare_entity("id6", "case 2", "context 2"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == ["case 1", "case 2"]
        assert pairs["case 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1"]["contender"]["id"] == "id5"
        assert pairs["case 2"]["baseline"]["id"] == "id3"
        assert pairs["case 2"]["contender"]["id"] == "id6"

    def test_contexts_dont_match_but_pair_them_anyway(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 2", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id3", "case 1", "context 3"),
            _fake_compare_entity("id4", "case 2", "context 4"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == ["case 1", "case 2"]
        assert pairs["case 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1"]["contender"]["id"] == "id3"
        assert pairs["case 2"]["baseline"]["id"] == "id2"
        assert pairs["case 2"]["contender"]["id"] == "id4"

    def test_multiple_contexts_for_same_cases(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 1", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id3", "case 1", "context 3"),
            _fake_compare_entity("id4", "case 1", "context 4"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 4
        assert list(pairs.keys()) == [
            "case 1-context 1",
            "case 1-context 2",
            "case 1-context 3",
            "case 1-context 4",
        ]
        assert pairs["case 1-context 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1-context 1"]["contender"] is None
        assert pairs["case 1-context 2"]["baseline"]["id"] == "id2"
        assert pairs["case 1-context 2"]["contender"] is None
        assert pairs["case 1-context 3"]["baseline"] is None
        assert pairs["case 1-context 3"]["contender"]["id"] == "id3"
        assert pairs["case 1-context 4"]["baseline"] is None
        assert pairs["case 1-context 4"]["contender"]["id"] == "id4"

    def test_multiple_contexts_for_same_cases_but_they_line_up(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 1", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id3", "case 1", "context 1"),
            _fake_compare_entity("id4", "case 1", "context 2"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == [
            "case 1-context 1",
            "case 1-context 2",
        ]
        assert pairs["case 1-context 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1-context 1"]["contender"]["id"] == "id3"
        assert pairs["case 1-context 2"]["baseline"]["id"] == "id2"
        assert pairs["case 1-context 2"]["contender"]["id"] == "id4"

    def test_multiple_contexts_for_same_cases_but_they_kinda_line_up(self):
        baselines = [
            _fake_compare_entity("id1", "case 1", "context 1"),
            _fake_compare_entity("id2", "case 1", "context 2"),
        ]
        contenders = [
            _fake_compare_entity("id3", "case 1", "context 1"),
        ]
        pairs = _get_pairs(baselines, contenders)
        assert len(pairs) == 2
        assert list(pairs.keys()) == [
            "case 1-context 1",
            "case 1-context 2",
        ]
        assert pairs["case 1-context 1"]["baseline"]["id"] == "id1"
        assert pairs["case 1-context 1"]["contender"]["id"] == "id3"
        assert pairs["case 1-context 2"]["baseline"]["id"] == "id2"
        assert pairs["case 1-context 2"]["contender"] is None


class TestCompareBenchmarksGet(_asserts.GetEnforcer):
    url = "/api/compare/benchmarks/{}/"
    public = True

    def _create(self, name=None, verbose=False):
        # create a distribution history & a regression
        _fixtures.summary(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            sha=_fixtures.GRANDPARENT,
        )
        summary_1 = _fixtures.summary(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            sha=_fixtures.PARENT,
        )
        summary_2 = _fixtures.summary(
            name=name,
            results=_fixtures.RESULTS_UP[2],
        )

        entity = FakeEntity(f"{summary_1.id}...{summary_2.id}")
        if verbose:
            return [summary_1, summary_2], entity
        return entity

    def test_compare(self, client):
        self.authenticate(client)
        name = _uuid()
        new_entities, compare = self._create(name, verbose=True)
        response = client.get(f"/api/compare/benchmarks/{compare.id}/")

        benchmark_ids = [e.id for e in new_entities]
        batch_ids = [e.batch_id for e in new_entities]
        run_ids = [e.run_id for e in new_entities]
        expected = _api_compare_entity(
            benchmark_ids,
            batch_ids,
            run_ids,
            name,
            CASE,
            tags={
                "dataset": "nyctaxi_sample",
                "cpu_count": 2,
                "file_type": "parquet",
                "input_type": "arrow",
                "compression": "snappy",
                "name": name,
            },
        )
        expected.update(
            {
                "baseline": "3.000 s",
                "contender": "20.000 s",
                "change": "-566.667%",
                "regression": True,
                "baseline_z_score": None,
                "contender_z_score": "-{:.3f}".format(_fixtures.Z_SCORE_UP),
                "contender_z_regression": True,
            }
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/benchmarks/foo...bar/")
        self.assert_404_not_found(response)


class TestCompareBatchesGet(_asserts.GetEnforcer):
    url = "/api/compare/batches/{}/"
    public = True

    def _create(self, verbose=False, run_id=None, batch_id=None):
        batch_id = batch_id if batch_id is not None else _uuid()
        summary_1 = _fixtures.summary(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary_2 = _fixtures.summary(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
        )
        entity = FakeEntity(f"{batch_id}...{batch_id}")
        if verbose:
            return [summary_1, summary_2], entity
        return entity

    def test_compare(self, client):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        new_entities, compare = self._create(
            verbose=True,
            run_id=run_id,
            batch_id=batch_id,
        )
        new_ids = [e.id for e in new_entities]
        response = client.get(f"/api/compare/batches/{compare.id}/")

        # cheating by comparing batch to same batch
        batch_ids = [batch_id, batch_id]
        run_ids = [run_id, run_id]
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
                    "cpu_count": 2,
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "read",
                },
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": 2,
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "write",
                },
            ],
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/batches/foo...bar/")
        self.assert_404_not_found(response)


class TestCompareRunsGet(_asserts.GetEnforcer):
    url = "/api/compare/runs/{}/"
    public = True

    def _create(self, verbose=False, run_id=None, batch_id=None):
        run_id = run_id if run_id is not None else _uuid()
        summary_1 = _fixtures.summary(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary_2 = _fixtures.summary(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
        )
        entity = FakeEntity(f"{run_id}...{run_id}")
        if verbose:
            return [summary_1, summary_2], entity
        return entity

    def test_compare(self, client):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        new_entities, compare = self._create(
            verbose=True,
            run_id=run_id,
            batch_id=batch_id,
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
                    "cpu_count": 2,
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "read",
                },
                {
                    "dataset": "nyctaxi_sample",
                    "cpu_count": 2,
                    "file_type": "parquet",
                    "input_type": "arrow",
                    "compression": "snappy",
                    "name": "write",
                },
            ],
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/runs/foo...bar/")
        self.assert_404_not_found(response)


class TestCompareCommitsGet(_asserts.GetEnforcer):
    url = "/api/compare/commits/{}/"
    public = True

    def _create(self, verbose=False):
        name = _uuid()
        contender = _fixtures.summary(
            name=name,
            sha=_fixtures.CHILD,
        )
        baseline = _fixtures.summary(
            name=name,
            sha=_fixtures.PARENT,
        )
        baseline_sha = baseline.run.commit.sha
        contender_sha = contender.run.commit.sha
        entity = FakeEntity(f"{baseline_sha}...{contender_sha}")

        if verbose:
            return [baseline.run, contender.run], entity
        return entity

    def test_compare(self, client):
        self.authenticate(client)
        [baseline, contender], compare = self._create(verbose=True)
        response = client.get(f"/api/compare/commits/{compare.id}/")
        expected = _api_compare_summary(
            baseline.commit.id,
            contender.commit.id,
            baseline.id,
            baseline.name,
            baseline.timestamp.isoformat(),
            contender.id,
            contender.name,
            contender.timestamp.isoformat(),
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get("/api/compare/commits/foo...bar/")
        self.assert_404_not_found(response)
