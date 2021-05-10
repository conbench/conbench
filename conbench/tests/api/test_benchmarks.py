import copy
import decimal
import uuid

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.distribution import Distribution
from ...entities.summary import Summary
from ...tests.api import _asserts


VALID_PAYLOAD = {
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "benchmark_language": "Python",
    },
    "run": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/apache/arrow",
    },
    "machine_info": {
        "architecture_name": "x86_64",
        "cpu_l1d_cache_bytes": "32768",
        "cpu_l1i_cache_bytes": "32768",
        "cpu_l2_cache_bytes": "262144",
        "cpu_l3_cache_bytes": "4194304",
        "cpu_core_count": "2",
        "cpu_frequency_max_hz": "3500000000",
        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
        "cpu_thread_count": "4",
        "kernel_name": "19.6.0",
        "memory_bytes": "17179869184",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "2a5709d179f349cba69ed242be3e6321",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
        "data": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "times": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "unit": "s",
        "time_unit": "s",
        "iqr": "0.030442",
        "iterations": 10,
        "max": "0.148896",
        "mean": "0.036369",
        "median": "0.008988",
        "min": "0.004733",
        "q1": "0.006500",
        "q3": "0.036942",
        "stdev": "0.049194",
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
    },
    "tags": {
        "compression": "snappy",
        "cpu_count": 2,
        "dataset": "nyctaxi_sample",
        "file_type": "parquet",
        "input_type": "arrow",
        "name": "file-write",
    },
}


def _expected_entity(summary):
    return _api_benchmark_entity(
        summary.id,
        summary.machine_id,
        summary.context_id,
        summary.case.id,
        summary.batch_id,
        summary.run_id,
        summary.case.name,
    )


def create_benchmark_summary(name=None, batch_id=None, run_id=None):
    data = copy.deepcopy(VALID_PAYLOAD)
    if name:
        data["tags"]["name"] = name
    if batch_id:
        data["stats"]["batch_id"] = batch_id
    if run_id:
        data["stats"]["run_id"] = run_id
    summary = Summary.create(data)
    return summary


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/api/benchmarks/{}/"
    public = True

    def _create(self):
        return create_benchmark_summary()

    def test_get_benchmark(self, client):
        self.authenticate(client)
        summary = self._create()
        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, _expected_entity(summary))


class TestBenchmarkDelete(_asserts.DeleteEnforcer):
    url = "/api/benchmarks/{}/"

    def test_delete_benchmark(self, client):
        self.authenticate(client)
        summary = create_benchmark_summary()

        # can get before delete
        Summary.one(id=summary.id)

        # delete
        response = client.delete(f"/api/benchmarks/{summary.id}/")
        self.assert_204_no_content(response)

        # cannot get after delete
        with pytest.raises(NotFound):
            Summary.one(id=summary.id)


class TestBenchmarkList(_asserts.ListEnforcer):
    url = "/api/benchmarks/"
    public = True

    def test_benchmark_list(self, client):
        self.authenticate(client)
        summary = create_benchmark_summary()
        response = client.get("/api/benchmarks/")
        self.assert_200_ok(response, contains=_expected_entity(summary))

    def test_benchmark_list_filter_by_name(self, client):
        self.authenticate(client)
        create_benchmark_summary(name="aaa")
        summary = create_benchmark_summary(name="bbb")
        create_benchmark_summary(name="ccc")
        response = client.get("/api/benchmarks/?name=bbb")
        self.assert_200_ok(response, [_expected_entity(summary)])

    def test_benchmark_list_filter_by_batch_id(self, client):
        self.authenticate(client)
        create_benchmark_summary(batch_id="10")
        summary = create_benchmark_summary(batch_id="20")
        create_benchmark_summary(batch_id="30")
        response = client.get("/api/benchmarks/?batch_id=20")
        self.assert_200_ok(response, [_expected_entity(summary)])

    def test_benchmark_list_filter_by_run_id(self, client):
        self.authenticate(client)
        create_benchmark_summary(run_id="100")
        summary = create_benchmark_summary(run_id="200")
        create_benchmark_summary(run_id="300")
        response = client.get("/api/benchmarks/?run_id=200")
        self.assert_200_ok(response, [_expected_entity(summary)])


class TestBenchmarkPost(_asserts.PostEnforcer):
    url = "/api/benchmarks/"
    required_fields = ["machine_info", "stats", "tags", "context", "run"]
    valid_payload = VALID_PAYLOAD

    def test_create_benchmark(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_benchmark_normalizes_data(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload)
        summary_1 = Summary.one(id=response.json["id"])
        data = copy.deepcopy(self.valid_payload)
        data["stats"]["run_id"] = data["stats"]["run_id"] + "_X"
        response = client.post("/api/benchmarks/", json=data)
        summary_2 = Summary.one(id=response.json["id"])
        assert summary_1.id != summary_2.id
        assert summary_1.case_id == summary_2.case_id
        assert summary_1.context_id == summary_2.context_id
        assert summary_1.machine_id == summary_2.machine_id
        assert summary_1.run_id != summary_2.run_id
        assert summary_1.run.commit_id == summary_2.run.commit_id

    def test_nested_schema_validation(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        del data["stats"]["iterations"]
        del data["machine_info"]["os_name"]
        data["stats"]["timestamp"] = None
        data["machine_info"]["os_version"] = None
        data["stats"]["extra"] = "field"
        data["machine_info"]["extra"] = "field"
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "machine_info": {
                "extra": ["Unknown field."],
                "os_name": ["Missing data for required field."],
                "os_version": ["Field may not be null."],
            },
            "stats": {
                "extra": ["Unknown field."],
                "iterations": ["Missing data for required field."],
                "timestamp": ["Field may not be null."],
            },
        }
        self.assert_400_bad_request(response, message)

    def test_create_benchmark_distribution(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["tags"]["name"] = uuid.uuid4().hex

        # first result
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary_1 = Summary.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary_1), location)
        case_id = summary_1.case_id

        # after one result
        distributions = Distribution.search(filters=[Distribution.case_id == case_id])
        assert len(distributions) == 1
        assert distributions[0].unit == "s"
        assert distributions[0].observations == 1
        assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
        assert distributions[0].mean_sd is None
        assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
        assert distributions[0].min_sd is None
        assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
        assert distributions[0].max_sd is None
        assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
        assert distributions[0].median_sd is None

        # second result
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary_2 = Summary.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary_2), location)
        assert summary_1.case_id == summary_2.case_id
        assert summary_1.context_id == summary_2.context_id
        assert summary_1.machine_id == summary_2.machine_id
        assert summary_1.run.commit_id == summary_2.run.commit_id

        # after two results
        distributions = Distribution.search(filters=[Distribution.case_id == case_id])
        assert len(distributions) == 1
        assert distributions[0].unit == "s"
        assert distributions[0].observations == 2
        assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
        assert distributions[0].mean_sd == decimal.Decimal("0")
        assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
        assert distributions[0].min_sd == decimal.Decimal("0")
        assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
        assert distributions[0].max_sd == decimal.Decimal("0")
        assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
        assert distributions[0].median_sd == decimal.Decimal("0")
