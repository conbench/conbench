import copy
import datetime
import uuid

from ...api._examples import _api_compare_entity, _api_compare_list
from ...entities.summary import Summary
from ...runner import Conbench
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


CASE = "snappy, cpu_count=2, parquet, arrow, nyctaxi_sample"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


def create_benchmark_summary(name, batch_id=None, run_id=None, results=None):
    data = copy.deepcopy(VALID_PAYLOAD)
    data["tags"]["name"] = name
    if batch_id:
        data["stats"]["batch_id"] = batch_id
    if run_id:
        data["stats"]["run_id"] = run_id
    if results is not None:
        conbench = Conbench()
        run_id = data["stats"]["run_id"]
        run_name = data["stats"]["run_name"]
        batch_id = data["stats"]["batch_id"]
        now = datetime.datetime.now(datetime.timezone.utc)
        data["stats"] = conbench._stats(
            results, "s", [], "s", now.isoformat(), run_id, run_name
        )
        data["stats"]["batch_id"] = batch_id
    summary = Summary.create(data)
    return summary


class TestCompareBenchmarksGet(_asserts.GetEnforcer):
    url = "/api/compare/benchmarks/{}/"
    public = True

    def _create(self, name=None, with_ids=False):
        if name is None:
            name = uuid.uuid4().hex

        # create a distribution history
        for _ in range(10):
            summary_1 = create_benchmark_summary(name, results=[1, 2, 3])

        # create a regression
        summary_2 = create_benchmark_summary(name, results=[4, 5, 6])

        entity = FakeEntity(f"{summary_1.id}...{summary_2.id}")
        if with_ids:
            return summary_1.id, summary_2.id, entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        name = uuid.uuid4().hex
        id_1, id_2, compare = self._create(name, with_ids=True)
        response = client.get(f"/api/compare/benchmarks/{compare.id}/")

        benchmark_ids = [id_1, id_2]
        batch_ids = [
            "7b2fdd9f929d47b9960152090d47f8e6",
            "7b2fdd9f929d47b9960152090d47f8e6",
        ]
        run_ids = [
            "2a5709d179f349cba69ed242be3e6321",
            "2a5709d179f349cba69ed242be3e6321",
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
                "baseline": "2.000 s",
                "contender": "5.000 s",
                "change": "150.000%",
                "regression": True,
                "baseline_z_score": "-0.302",
                "contender_z_score": "3.015",
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
        if batch_id is None:
            batch_id = uuid.uuid4().hex
        summary1 = create_benchmark_summary(
            "read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary2 = create_benchmark_summary(
            "write",
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
        run_id, batch_id = uuid.uuid4().hex, uuid.uuid4().hex
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
        if run_id is None:
            run_id = uuid.uuid4().hex
        summary1 = create_benchmark_summary(
            "read",
            run_id=run_id,
            batch_id=batch_id,
        )
        summary2 = create_benchmark_summary(
            "write",
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
        run_id, batch_id = uuid.uuid4().hex, uuid.uuid4().hex
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
