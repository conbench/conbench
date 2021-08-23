from ...api._examples import _api_compare_entity, _api_compare_list
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

CASE = "snappy, cpu_count=2, parquet, arrow, nyctaxi_sample"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


class TestCompareBenchmarksGet(_asserts.GetEnforcer):
    url = "/api/compare/benchmarks/{}/"
    public = True

    def _create(self, name=None, with_ids=False):
        # create a distribution history & a regression
        name = name if name is not None else _uuid()
        run_0, run_1, run_2 = _uuid(), _uuid(), _uuid()
        _fixtures.create_benchmark_summary(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            run_id=run_0,
            sha=_fixtures.GRANDPARENT,
        )
        summary_1 = _fixtures.create_benchmark_summary(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            run_id=run_1,
            sha=_fixtures.PARENT,
        )
        summary_2 = _fixtures.create_benchmark_summary(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            run_id=run_2,
        )

        entity = FakeEntity(f"{summary_1.id}...{summary_2.id}")
        if with_ids:
            return summary_1.id, summary_2.id, run_1, run_2, entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        name = _uuid()
        id_1, id_2, run_1, run_2, compare = self._create(name, with_ids=True)
        response = client.get(f"/api/compare/benchmarks/{compare.id}/")

        benchmark_ids = [id_1, id_2]
        run_ids = [run_1, run_2]
        batch_ids = [
            "7b2fdd9f929d47b9960152090d47f8e6",
            "7b2fdd9f929d47b9960152090d47f8e6",
        ]
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

    def _create(self, with_ids=False, run_id=None, batch_id=None):
        batch_id = batch_id if batch_id is not None else _uuid()
        summary1 = _fixtures.create_benchmark_summary(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary2 = _fixtures.create_benchmark_summary(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
        )
        entity = FakeEntity(f"{batch_id}...{batch_id}")
        if with_ids:
            return [summary1.id, summary2.id], entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        new_ids, compare = self._create(
            with_ids=True,
            run_id=run_id,
            batch_id=batch_id,
        )
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

    def _create(self, with_ids=False, run_id=None, batch_id=None):
        run_id = run_id if run_id is not None else _uuid()
        summary1 = _fixtures.create_benchmark_summary(
            name="read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary2 = _fixtures.create_benchmark_summary(
            name="write",
            run_id=run_id,
            batch_id=batch_id,
        )
        entity = FakeEntity(f"{run_id}...{run_id}")
        if with_ids:
            return [summary1.id, summary2.id], entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        run_id, batch_id = _uuid(), _uuid()
        new_ids, compare = self._create(
            with_ids=True,
            run_id=run_id,
            batch_id=batch_id,
        )
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
