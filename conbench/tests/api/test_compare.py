import copy
import uuid

from ...api._examples import _api_compare_entity, _api_compare_list
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


CASE = "snappy, nyctaxi_sample, parquet, arrow"


class FakeEntity:
    def __init__(self, _id):
        self.id = _id


def create_benchmark_summary(name, batch_id=None, run_id=None):
    data = copy.deepcopy(VALID_PAYLOAD)
    data["tags"]["name"] = name
    if batch_id:
        data["stats"]["batch_id"] = batch_id
    if run_id:
        data["stats"]["run_id"] = run_id
    summary = Summary.create(data)
    return summary


class TestCompareBenchmarksGet(_asserts.GetEnforcer):
    url = "/api/compare/benchmarks/{}/"
    public = True

    def _create(self, with_ids=False):
        summary = create_benchmark_summary("read")
        entity = FakeEntity(f"{summary.id}...{summary.id}")
        if with_ids:
            return summary.id, entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        new_id, compare = self._create(with_ids=True)
        response = client.get(f"/api/compare/benchmarks/{compare.id}/")

        # cheating by comparing benchmark to same benchmark
        benchmark_ids = [new_id, new_id]
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
            "read",
            CASE,
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get(f"/api/compare/benchmarks/foo...bar/")
        self.assert_404_not_found(response)


class TestCompareBacthesGet(_asserts.GetEnforcer):
    url = "/api/compare/batches/{}/"
    public = True

    def _create(self, with_ids=False, batch_id=None):
        if batch_id is None:
            batch_id = uuid.uuid4().hex
        summary1 = create_benchmark_summary("read", batch_id=batch_id)
        summary2 = create_benchmark_summary("write", batch_id=batch_id)
        entity = FakeEntity(f"{batch_id}...{batch_id}")
        if with_ids:
            return [summary1.id, summary2.id], entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        batch_id = uuid.uuid4().hex
        new_ids, compare = self._create(with_ids=True, batch_id=batch_id)
        response = client.get(f"/api/compare/batches/{compare.id}/")

        # cheating by comparing batch to same batch
        batch_ids = [batch_id, batch_id]
        run_ids = [
            "2a5709d179f349cba69ed242be3e6321",
            "2a5709d179f349cba69ed242be3e6321",
        ]
        batches = ["read", "write"]
        benchmarks = [CASE, CASE]
        expected = _api_compare_list(
            new_ids,
            new_ids,
            batch_ids,
            run_ids,
            batches,
            benchmarks,
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get(f"/api/compare/batches/foo...bar/")
        self.assert_404_not_found(response)


class TestCompareRunsGet(_asserts.GetEnforcer):
    url = "/api/compare/runs/{}/"
    public = True

    def _create(self, with_ids=False, run_id=None):
        if run_id is None:
            run_id = uuid.uuid4().hex
        summary1 = create_benchmark_summary("read", run_id=run_id)
        summary2 = create_benchmark_summary("write", run_id=run_id)
        entity = FakeEntity(f"{run_id}...{run_id}")
        if with_ids:
            return [summary1.id, summary2.id], entity
        else:
            return entity

    def test_compare(self, client):
        self.authenticate(client)
        run_id = uuid.uuid4().hex
        new_ids, compare = self._create(with_ids=True, run_id=run_id)
        response = client.get(f"/api/compare/runs/{compare.id}/")

        # cheating by comparing run to same run
        run_ids = [run_id, run_id]
        batch_ids = [
            "7b2fdd9f929d47b9960152090d47f8e6",
            "7b2fdd9f929d47b9960152090d47f8e6",
        ]
        batches = ["read", "write"]
        benchmarks = [CASE, CASE]
        expected = _api_compare_list(
            new_ids,
            new_ids,
            batch_ids,
            run_ids,
            batches,
            benchmarks,
        )
        self.assert_200_ok(response, expected)

    def test_compare_unknown_compare_ids(self, client):
        self.authenticate(client)
        response = client.get(f"/api/compare/runs/foo...bar/")
        self.assert_404_not_found(response)
