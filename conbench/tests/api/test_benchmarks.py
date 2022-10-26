import copy
import decimal

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.benchmark_result import BenchmarkResult
from ...entities.distribution import Distribution
from ...entities.run import Run
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

ARROW_REPO = "https://github.com/apache/arrow"
CONBENCH_REPO = "https://github.com/conbench/conbench"


def _expected_entity(benchmark_result):
    return _api_benchmark_entity(
        benchmark_result.id,
        benchmark_result.case_id,
        benchmark_result.info_id,
        benchmark_result.context_id,
        benchmark_result.batch_id,
        benchmark_result.run_id,
        benchmark_result.case.name,
        benchmark_result.error,
        benchmark_result.validation,
        benchmark_result.optional_benchmark_info,
    )


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/api/benchmarks/{}/"
    public = True

    def _create(self, name=None, results=None, unit=None, sha=None):
        return _fixtures.benchmark_result(
            name=name,
            results=results,
            unit=unit,
            sha=sha,
        )

    def test_get_benchmark(self, client):
        self.authenticate(client)
        benchmark_result = self._create()
        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, _expected_entity(benchmark_result))

    def test_get_benchmark_regression(self, client):
        self.authenticate(client)

        name = _uuid()

        # create a distribution history & a regression
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[0],
            unit="i/s",
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[1],
            unit="i/s",
            sha=_fixtures.PARENT,
        )
        benchmark_result = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="i/s",
        )

        expected = _expected_entity(benchmark_result)
        expected["stats"].update(
            {
                "data": [1.0, 2.0, 3.0],
                "iqr": 1.0,
                "iterations": 3,
                "max": 3.0,
                "mean": 2.0,
                "median": 2.0,
                "min": 1.0,
                "q1": 1.5,
                "q3": 2.5,
                "stdev": 1.0,
                "times": [],
                "z_score": -abs(_fixtures.Z_SCORE_DOWN_COMPUTED_VIA_POSTGRES),
                "z_regression": True,
                "unit": "i/s",
            }
        )

        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_regression_less_is_better(self, client):
        self.authenticate(client)

        name = _uuid()

        # create a distribution history & a regression
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            unit="s",
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            unit="s",
            sha=_fixtures.PARENT,
        )
        benchmark_result = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="s",
        )

        expected = _expected_entity(benchmark_result)
        expected["stats"].update(
            {
                "data": [10.0, 20.0, 30.0],
                "iqr": 10.0,
                "iterations": 3,
                "max": 30.0,
                "mean": 20.0,
                "median": 20.0,
                "min": 10.0,
                "q1": 15.0,
                "q3": 25.0,
                "stdev": 10.0,
                "times": [],
                "z_score": -abs(_fixtures.Z_SCORE_UP_COMPUTED_VIA_POSTGRES),
                "z_regression": True,
            }
        )

        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_improvement(self, client):
        self.authenticate(client)

        name = _uuid()

        # create a distribution history & a improvement
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            unit="i/s",
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            unit="i/s",
            sha=_fixtures.PARENT,
        )
        benchmark_result = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="i/s",
        )

        expected = _expected_entity(benchmark_result)
        expected["stats"].update(
            {
                "data": [10.0, 20.0, 30.0],
                "iqr": 10.0,
                "iterations": 3,
                "max": 30.0,
                "mean": 20.0,
                "median": 20.0,
                "min": 10.0,
                "q1": 15.0,
                "q3": 25.0,
                "stdev": 10.0,
                "times": [],
                "z_score": abs(_fixtures.Z_SCORE_UP_COMPUTED_VIA_POSTGRES),
                "z_improvement": True,
                "unit": "i/s",
            }
        )

        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_improvement_less_is_better(self, client):
        self.authenticate(client)

        name = _uuid()

        # create a distribution history & a improvement
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[0],
            unit="s",
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[1],
            unit="s",
            sha=_fixtures.PARENT,
        )
        benchmark_result = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="s",
        )

        expected = _expected_entity(benchmark_result)
        expected["stats"].update(
            {
                "data": [1.0, 2.0, 3.0],
                "iqr": 1.0,
                "iterations": 3,
                "max": 3.0,
                "mean": 2.0,
                "median": 2.0,
                "min": 1.0,
                "q1": 1.5,
                "q3": 2.5,
                "stdev": 1.0,
                "times": [],
                "z_score": abs(_fixtures.Z_SCORE_DOWN_COMPUTED_VIA_POSTGRES),
                "z_improvement": True,
            }
        )

        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, expected)


class TestBenchmarkDelete(_asserts.DeleteEnforcer):
    url = "/api/benchmarks/{}/"

    def test_delete_benchmark(self, client):
        self.authenticate(client)
        benchmark_result = _fixtures.benchmark_result()

        # can get before delete
        BenchmarkResult.one(id=benchmark_result.id)

        # delete
        response = client.delete(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_204_no_content(response)

        # cannot get after delete
        with pytest.raises(NotFound):
            BenchmarkResult.one(id=benchmark_result.id)


class TestBenchmarkList(_asserts.ListEnforcer):
    url = "/api/benchmarks/"
    public = True

    def test_benchmark_list(self, client):
        self.authenticate(client)
        benchmark_result = _fixtures.benchmark_result()
        response = client.get("/api/benchmarks/")
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result))

    def test_benchmark_list_filter_by_name(self, client):
        self.authenticate(client)
        _fixtures.benchmark_result(name="aaa")
        benchmark_result = _fixtures.benchmark_result(name="bbb")
        _fixtures.benchmark_result(name="ccc")
        response = client.get("/api/benchmarks/?name=bbb")
        self.assert_200_ok(response, [_expected_entity(benchmark_result)])

    def test_benchmark_list_filter_by_batch_id(self, client):
        self.authenticate(client)
        benchmark_result = _fixtures.benchmark_result(batch_id="20")
        response = client.get("/api/benchmarks/?batch_id=20")
        self.assert_200_ok(response, [_expected_entity(benchmark_result)])

    def test_benchmark_list_filter_by_multiple_batch_id(self, client):
        self.authenticate(client)
        benchmark_result_1 = _fixtures.benchmark_result()
        batch_id_1 = benchmark_result_1.batch_id
        benchmark_result_2 = _fixtures.benchmark_result()
        batch_id_2 = benchmark_result_2.batch_id
        response = client.get(f"/api/benchmarks/?batch_id={batch_id_1},{batch_id_2}")
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result_1))
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result_2))

    def test_benchmark_list_filter_by_run_id(self, client):
        self.authenticate(client)
        _fixtures.benchmark_result(run_id="100")
        benchmark_result = _fixtures.benchmark_result(run_id="200")
        _fixtures.benchmark_result(run_id="300")
        response = client.get("/api/benchmarks/?run_id=200")
        self.assert_200_ok(response, [_expected_entity(benchmark_result)])

    def test_benchmark_list_filter_by_multiple_run_id(self, client):
        self.authenticate(client)
        benchmark_result_1 = _fixtures.benchmark_result()
        run_id_1 = benchmark_result_1.run_id
        benchmark_result_2 = _fixtures.benchmark_result()
        run_id_2 = benchmark_result_2.run_id
        response = client.get(f"/api/benchmarks/?run_id={run_id_1},{run_id_2}")
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result_1))
        self.assert_200_ok(response, contains=_expected_entity(benchmark_result_2))


class TestBenchmarkPost(_asserts.PostEnforcer):
    url = "/api/benchmarks/"
    valid_payload = _fixtures.VALID_PAYLOAD
    valid_payload_for_cluster = _fixtures.VALID_PAYLOAD_FOR_CLUSTER
    valid_payload_with_error = _fixtures.VALID_PAYLOAD_WITH_ERROR
    required_fields = [
        "batch_id",
        "context",
        "info",
        "run_id",
        "tags",
        "timestamp",
    ]

    def test_create_benchmark(self, client):
        for hardware_type, payload in [
            ("machine", self.valid_payload),
            ("cluster", self.valid_payload_for_cluster),
        ]:
            self.authenticate(client)
            response = client.post("/api/benchmarks/", json=payload)
            new_id = response.json["id"]
            benchmark_result = BenchmarkResult.one(id=new_id)
            location = "http://localhost/api/benchmarks/%s/" % new_id
            self.assert_201_created(
                response, _expected_entity(benchmark_result), location
            )

            assert benchmark_result.run.hardware.type == hardware_type
            for attr, value in payload[f"{hardware_type}_info"].items():
                assert getattr(benchmark_result.run.hardware, attr) == value or getattr(
                    benchmark_result.run.hardware, attr
                ) == int(value)

    def test_create_benchmark_after_run_was_created(self, client):
        for hardware_type, run_payload, benchmark_results_payload in [
            ("machine", _fixtures.VALID_RUN_PAYLOAD, self.valid_payload),
            (
                "cluster",
                _fixtures.VALID_RUN_PAYLOAD_FOR_CLUSTER,
                self.valid_payload_for_cluster,
            ),
        ]:
            self.authenticate(client)
            client.post("/api/runs/", json=run_payload)
            run_id = run_payload["id"]
            benchmark_results_payload["run_id"] = run_id
            response = client.post("/api/benchmarks/", json=benchmark_results_payload)
            new_id = response.json["id"]
            benchmark_result = BenchmarkResult.one(id=new_id)
            assert benchmark_result.run_id == run_id
            location = f"http://localhost/api/benchmarks/{new_id}/"
            self.assert_201_created(
                response, _expected_entity(benchmark_result), location
            )

            assert benchmark_result.run.hardware.type == hardware_type
            for attr, value in benchmark_results_payload[
                f"{hardware_type}_info"
            ].items():
                assert getattr(benchmark_result.run.hardware, attr) == value or getattr(
                    benchmark_result.run.hardware, attr
                ) == int(value)

    def test_create_benchmark_with_error(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_with_error)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_benchmark_with_error_after_run_was_created(self, client):
        self.authenticate(client)
        run_payload = _fixtures.VALID_RUN_PAYLOAD
        benchmark_results_payload = self.valid_payload_with_error
        benchmark_results_payload["run_id"] = run_payload["id"]
        client.post("/api/runs/", json=run_payload)
        assert Run.one(id=run_payload["id"]).has_errors is False

        response = client.post("/api/benchmarks/", json=benchmark_results_payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = f"http://localhost/api/benchmarks/{new_id}/"
        self.assert_201_created(response, _expected_entity(benchmark_result), location)
        assert Run.one(id=run_payload["id"]).has_errors is True

    def test_create_benchmark_for_cluster_with_optional_info_changed(self, client):
        # Post benchmarks for cluster-1
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_for_cluster)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        hardware_id = benchmark_result.run.hardware.id

        # Post benchmarks for cluster-1 with different optional_info but the same cluster name and info
        payload = copy.deepcopy(self.valid_payload_for_cluster)
        payload["cluster_info"]["optional_info"] = {"field": 1}
        payload["run_id"] = _uuid()
        response = client.post("/api/benchmarks/", json=payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.hardware.id == hardware_id
        assert (
            benchmark_result.run.hardware.optional_info
            == payload["cluster_info"]["optional_info"]
        )

    def test_create_benchmark_for_cluster_with_info_changed(self, client):
        # Post benchmarks for cluster-1
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_for_cluster)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        hardware_id = benchmark_result.run.hardware.id

        # Post benchmarks for cluster-1 with different info but the same cluster name and optional_info
        payload = copy.deepcopy(self.valid_payload_for_cluster)
        payload["cluster_info"]["info"] = {"field": 1}
        payload["run_id"] = _uuid()
        response = client.post("/api/benchmarks/", json=payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.hardware.id != hardware_id
        assert benchmark_result.run.hardware.info == payload["cluster_info"]["info"]

    def test_create_benchmark_normalizes_data(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload)
        benchmark_result_1 = BenchmarkResult.one(id=response.json["id"])
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = data["run_id"] + "_X"
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result_2 = BenchmarkResult.one(id=response.json["id"])
        assert benchmark_result_1.id != benchmark_result_2.id
        assert benchmark_result_1.case_id == benchmark_result_2.case_id
        assert benchmark_result_1.info_id == benchmark_result_2.info_id
        assert benchmark_result_1.context_id == benchmark_result_2.context_id
        assert benchmark_result_1.run.hardware_id == benchmark_result_2.run.hardware_id
        assert benchmark_result_1.run_id != benchmark_result_2.run_id
        assert benchmark_result_1.run.commit_id == benchmark_result_2.run.commit_id

    def test_create_benchmark_can_specify_run_and_batch_id(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        run_id, batch_id = _uuid(), _uuid()
        data["run_id"] = run_id
        data["batch_id"] = batch_id
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result = BenchmarkResult.one(id=response.json["id"])
        assert benchmark_result.run_id == run_id
        assert benchmark_result.batch_id == batch_id

    def test_create_benchmark_cannot_omit_batch_id(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)

        # omit
        del data["batch_id"]
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "batch_id": ["Missing data for required field."],
        }
        self.assert_400_bad_request(response, message)

        # null
        data["batch_id"] = None
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "batch_id": ["Field may not be null."],
        }
        self.assert_400_bad_request(response, message)

    def test_create_benchmark_cannot_omit_run_id(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)

        # omit
        del data["run_id"]
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "run_id": ["Missing data for required field."],
        }
        self.assert_400_bad_request(response, message)

        # null
        data["run_id"] = None
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "run_id": ["Field may not be null."],
        }
        self.assert_400_bad_request(response, message)

    def test_nested_schema_validation(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        del data["stats"]["iterations"]
        del data["github"]["commit"]
        del data["machine_info"]["os_name"]
        data["machine_info"]["os_version"] = None
        data["stats"]["extra"] = "field"
        data["github"]["extra"] = "field"
        data["machine_info"]["extra"] = "field"
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "github": {
                "extra": ["Unknown field."],
                "commit": ["Missing data for required field."],
            },
            "machine_info": {
                "extra": ["Unknown field."],
                "os_name": ["Missing data for required field."],
                "os_version": ["Field may not be null."],
            },
            "stats": {
                "extra": ["Unknown field."],
                "iterations": ["Missing data for required field."],
            },
        }
        self.assert_400_bad_request(response, message)

    def _assert_none_commit(self, response):
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == ""
        assert benchmark_result.run.commit.repository == ""
        assert benchmark_result.run.commit.parent is None
        return benchmark_result, new_id

    def test_create_no_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        del data["github"]

        # create benchmark without commit context
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # create another benchmark without commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_empty_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = ""

        # create benchmark without commit context
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # create another benchmark without commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_unknown_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "unknown commit"
        data["github"]["repository"] = ARROW_REPO

        # create benchmark with unknown commit context
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == "unknown commit"
        assert benchmark_result.run.commit.repository == ARROW_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # create another benchmark with unknown commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == "unknown commit"
        assert benchmark_result.run.commit.repository == ARROW_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_different_git_repo_format(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with git@g"
        data["github"]["repository"] = "git@github.com:apache/arrow"

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == "testing repository with git@g"
        assert benchmark_result.run.commit.repository == ARROW_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_repo_not_full_url(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with just org/repo"
        data["github"]["repository"] = "apache/arrow"

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert (
            benchmark_result.run.commit.sha == "testing repository with just org/repo"
        )
        assert benchmark_result.run.commit.repository == ARROW_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_allow_just_repository(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = ARROW_REPO

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == ""
        assert benchmark_result.run.commit.repository == ARROW_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # And again with a different repository with an empty sha
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = CONBENCH_REPO

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == ""
        assert benchmark_result.run.commit.repository == CONBENCH_REPO
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_allow_just_sha(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "something something"
        data["github"]["repository"] = ""

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.run.commit.sha == "something something"
        assert benchmark_result.run.commit.repository == ""
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_benchmark_distribution(self, client):
        for payload in [self.valid_payload, self.valid_payload_for_cluster]:
            self.authenticate(client)
            data = copy.deepcopy(payload)
            data["tags"]["name"] = _uuid()

            # first result
            response = client.post("/api/benchmarks/", json=data)
            new_id = response.json["id"]
            benchmark_result_1 = BenchmarkResult.one(id=new_id)
            location = "http://localhost/api/benchmarks/%s/" % new_id
            self.assert_201_created(
                response, _expected_entity(benchmark_result_1), location
            )
            case_id = benchmark_result_1.case_id

            # after one result
            distributions = Distribution.all(case_id=case_id)
            assert len(distributions) == 1
            assert distributions[0].unit == "s"
            assert distributions[0].observations == 1
            assert distributions[0].mean_mean == decimal.Decimal(
                "0.03636900000000000000"
            )
            assert distributions[0].mean_sd is None
            assert distributions[0].min_mean == decimal.Decimal(
                "0.00473300000000000000"
            )
            assert distributions[0].min_sd is None
            assert distributions[0].max_mean == decimal.Decimal(
                "0.14889600000000000000"
            )
            assert distributions[0].max_sd is None
            assert distributions[0].median_mean == decimal.Decimal(
                "0.00898800000000000000"
            )
            assert distributions[0].median_sd is None

            # second result
            response = client.post("/api/benchmarks/", json=data)
            new_id = response.json["id"]
            benchmark_result_2 = BenchmarkResult.one(id=new_id)
            location = "http://localhost/api/benchmarks/%s/" % new_id
            self.assert_201_created(
                response, _expected_entity(benchmark_result_2), location
            )
            assert benchmark_result_1.case_id == benchmark_result_2.case_id
            assert benchmark_result_1.context_id == benchmark_result_2.context_id
            assert (
                benchmark_result_1.run.hardware_id == benchmark_result_2.run.hardware_id
            )
            assert benchmark_result_1.run.commit_id == benchmark_result_2.run.commit_id

            # after two results
            distributions = Distribution.all(case_id=case_id)
            assert len(distributions) == 1
            assert distributions[0].unit == "s"
            assert distributions[0].observations == 2
            assert distributions[0].mean_mean == decimal.Decimal(
                "0.03636900000000000000"
            )
            assert distributions[0].mean_sd == decimal.Decimal("0")
            assert distributions[0].min_mean == decimal.Decimal(
                "0.00473300000000000000"
            )
            assert distributions[0].min_sd == decimal.Decimal("0")
            assert distributions[0].max_mean == decimal.Decimal(
                "0.14889600000000000000"
            )
            assert distributions[0].max_sd == decimal.Decimal("0")
            assert distributions[0].median_mean == decimal.Decimal(
                "0.00898800000000000000"
            )
            assert distributions[0].median_sd == decimal.Decimal("0")

    def test_valid_payload_with_optional_benchmark_info(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        assert benchmark_result.optional_benchmark_info == {
            "trace_id": "some trace id",
            "logs": "some log uri",
        }
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_one_hardware_field_is_present(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        del data["machine_info"]
        response = client.post(self.url, json=data)
        message = {"_schema": ["Either machine_info or cluster_info field is required"]}
        self.assert_400_bad_request(response, message)

    def test_two_hardware_fields_are_present(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["cluster_info"] = {
            "name": "cluster",
            "info": {"field": 1},
            "optional_info": {},
        }
        response = client.post(self.url, json=data)
        message = {
            "_schema": [
                "machine_info and cluster_info fields can not be used at the same time"
            ]
        }
        self.assert_400_bad_request(response, message)

    def test_neither_stats_nor_error_field_is_present(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        del data["stats"]
        response = client.post(self.url, json=data)
        message = {"_schema": ["Either stats or error field is required"]}
        self.assert_400_bad_request(response, message)

    def test_stats_and_error_fields_are_present(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["error"] = {}
        response = client.post(self.url, json=data)
        message = {
            "_schema": ["stats and error fields can not be used at the same time"]
        }
        self.assert_400_bad_request(response, message)
