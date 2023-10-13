import copy
import datetime
from typing import Tuple

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.benchmark_result import BenchmarkResult
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

ARROW_REPO = "https://github.com/apache/arrow"
CONBENCH_REPO = "https://github.com/conbench/conbench"


def _expected_entity(benchmark_result: BenchmarkResult, stats=None):
    if benchmark_result.commit:
        parent = benchmark_result.commit.get_parent_commit()
        parent_id = parent.id if parent else None
        commit_type = "known" if benchmark_result.commit.timestamp else "unknown"
        branch = benchmark_result.commit.branch
    else:
        parent_id = None
        commit_type = "none"
        branch = None

    return _api_benchmark_entity(
        benchmark_result.id,
        benchmark_result.info_id,
        benchmark_result.context_id,
        benchmark_result.batch_id,
        benchmark_result.run_id,
        benchmark_result.run_tags,
        benchmark_result.run_reason,
        benchmark_result.commit_id,
        parent_id,
        commit_type,
        benchmark_result.commit_repo_url,
        branch,
        benchmark_result.hardware_id,
        benchmark_result.hardware.name,
        benchmark_result.hardware.type,
        benchmark_result.case.name,
        benchmark_result.history_fingerprint,
        stats,
        benchmark_result.error,
        benchmark_result.validation,
        benchmark_result.optional_benchmark_info,
        benchmark_result.timestamp,
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
            }
        )

        response = client.get(f"/api/benchmarks/{benchmark_result.id}/")
        self.assert_200_ok(response, expected)


class TestBenchmarkUpdate(_asserts.PutEnforcer):
    url = "/api/benchmarks/{}/"
    valid_payload = {"change_annotations": {"a": True, "b": None}}

    def _create_entity_to_update(self):
        return _fixtures.benchmark_result()

    def test_update_change_annotations(self, client):
        self.authenticate(client)
        benchmark_result = self._create_entity_to_update()
        assert benchmark_result.change_annotations == {}

        expected = _expected_entity(benchmark_result)
        expected["change_annotations"]["a"] = True
        expected["change_annotations"]["b"] = "testing"

        response = client.put(
            self.url.format(benchmark_result.id),
            json={"change_annotations": {"a": True, "b": "testing"}},
        )
        self.assert_200_ok(response, expected)

        # ensure GET now returns the updated change_annotations
        response = client.get(self.url.format(benchmark_result.id))
        self.assert_200_ok(response, expected)

        # delete a key and add a different key
        del expected["change_annotations"]["b"]
        expected["change_annotations"]["c"] = 4

        response = client.put(
            self.url.format(benchmark_result.id),
            json={"change_annotations": {"b": None, "c": 4}},
        )
        self.assert_200_ok(response, expected)

        # ensure GET now returns the updated change_annotations
        response = client.get(self.url.format(benchmark_result.id))
        self.assert_200_ok(response, expected)

        # ensure that PUTting {} will leave them all unchanged
        response = client.put(
            self.url.format(benchmark_result.id), json={"change_annotations": {}}
        )
        self.assert_200_ok(response, expected)
        response = client.get(self.url.format(benchmark_result.id))
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

    def _make_request(self, client, **kwargs) -> dict:
        """Hit this endpoint with the query args given in kwargs. Make sure it returns a
        200 and return the jsonified response.

        If any kwarg value is None, don't include that query arg in the request.
        """
        query_args = [
            f"{key}={value}" for key, value in kwargs.items() if value is not None
        ]
        query_str = f"{self.url}?" + "&".join(query_args)
        response = client.get(query_str)
        self.assert_200_ok(response)
        return response.json

    def _request_all(self, client, **kwargs) -> Tuple[list, int]:
        """Paginate over benchmark results, and return 1) a list of all results that
        matched the filters, and 2) how many pages were hit.
        """
        benchmark_results = []
        pages_hit = 0

        res = self._make_request(client, **kwargs)
        pages_hit += 1
        benchmark_results += res["data"]

        while res["metadata"]["next_page_cursor"]:
            res = self._make_request(
                client, cursor=res["metadata"]["next_page_cursor"], **kwargs
            )
            pages_hit += 1
            benchmark_results += res["data"]

        return benchmark_results, pages_hit

    @classmethod
    def setup_class(cls):
        """Special pytest method - do this once before running the tests in this class."""
        # set up 210 fake results from 2023-10-01 to 2023-10-09 17:00:00
        timestamp = datetime.datetime(2023, 10, 1)
        for run_id in ["1", "2"]:  # 2
            for name in ["a", "b", "c"]:  # 3
                for batch_id in ["3", "4", "5", "6", "7"]:  # 5
                    for run_reason in ["d", "e", "f", "g", "h", "i", "j"]:  # 7
                        _fixtures.benchmark_result(
                            name=name,
                            batch_id=batch_id,
                            run_id=run_id,
                            reason=run_reason,
                            timestamp=timestamp.isoformat(),
                        )
                        timestamp += datetime.timedelta(hours=1)

        # ...and another that's too old to be returned without specifying run_id
        _fixtures.benchmark_result(
            name="a", batch_id="3", run_id="1", reason="d", timestamp="2000-01-01"
        )

    @pytest.fixture(autouse=True)
    def clear_db_state_between_tests(self):
        """Override this autoused fixture from conftest.py so we don't delete that fake
        data between the tests in this class.
        """
        return

    # Try all the combinations of filters and different page sizes
    @pytest.mark.parametrize("run_id_arg", ["1", None])
    @pytest.mark.parametrize("name_arg", ["a", None])
    @pytest.mark.parametrize("batch_id_arg", ["3", None])
    @pytest.mark.parametrize("run_reason_arg", ["d", None])
    @pytest.mark.parametrize("page_size_arg", [2, 1000])
    def test_benchmark_list(
        self, client, run_id_arg, name_arg, batch_id_arg, run_reason_arg, page_size_arg
    ):
        self.authenticate(client)

        # Find the expected number of filtered results
        expected_num_results = 210
        if name_arg:
            expected_num_results /= 3
        if batch_id_arg:
            expected_num_results /= 5
        if run_reason_arg:
            expected_num_results /= 7
        if run_id_arg:
            expected_num_results /= 2
            # add one for the "old" result
            expected_num_results += 1

        benchmark_results, pages_hit = self._request_all(
            client,
            run_id=run_id_arg,
            name=name_arg,
            batch_id=batch_id_arg,
            run_reason=run_reason_arg,
            page_size=page_size_arg,
        )
        assert len(benchmark_results) == expected_num_results
        assert pages_hit == (expected_num_results // page_size_arg) + 1

    @pytest.mark.parametrize("earliest_timestamp_arg", ["2023-10-02", None])
    @pytest.mark.parametrize("latest_timestamp_arg", ["2023-10-09", None])
    def test_benchmark_list_time_filters(
        self, client, earliest_timestamp_arg, latest_timestamp_arg
    ):
        self.authenticate(client)

        # Find the expected number of filtered results
        expected_num_results = 210
        if earliest_timestamp_arg:
            expected_num_results -= 24
        if latest_timestamp_arg:
            expected_num_results -= 17

        benchmark_results, pages_hit = self._request_all(
            client,
            earliest_timestamp=earliest_timestamp_arg,
            latest_timestamp=latest_timestamp_arg,
            page_size=1000,  # no pagination
        )
        assert len(benchmark_results) == expected_num_results
        assert pages_hit == 1

    @pytest.mark.parametrize("page_size", ["0", "1001", "-1", "asd"])
    def test_bad_page_size(self, client, page_size):
        self.authenticate(client)
        res = client.get(f"{self.url}?page_size={page_size}")
        self.assert_400_bad_request(
            res,
            {"_errors": ["page_size must be a positive integer no greater than 1000"]},
        )


class TestBenchmarkResultPost(_asserts.PostEnforcer):
    url = "/api/benchmarks/"
    valid_payload = _fixtures.VALID_RESULT_PAYLOAD
    valid_payload_for_cluster = _fixtures.VALID_RESULT_PAYLOAD_FOR_CLUSTER
    valid_payload_with_error = _fixtures.VALID_RESULT_PAYLOAD_WITH_ERROR
    valid_payload_with_iteration_error = (
        _fixtures.VALID_RESULT_PAYLOAD_WITH_ITERATION_ERROR
    )
    required_fields = [
        "batch_id",  # why is this required?
        "context",
        # should this be optional in the future? grouping results in a run can
        # be convenient, but should not be necessary.
        "run_id",
        "tags",
        "timestamp",
        "github",
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

            assert benchmark_result.hardware.type == hardware_type
            for attr, value in payload[f"{hardware_type}_info"].items():
                assert getattr(benchmark_result.hardware, attr) == value or getattr(
                    benchmark_result.hardware, attr
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

            assert benchmark_result.hardware.type == hardware_type
            for attr, value in benchmark_results_payload[
                f"{hardware_type}_info"
            ].items():
                assert getattr(benchmark_result.hardware, attr) == value or getattr(
                    benchmark_result.hardware, attr
                ) == int(value)

    def test_create_benchmark_with_error(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_with_error)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    @pytest.mark.parametrize("with_error_property", [True, False])
    def test_create_benchmark_with_one_iteration_error(
        self, client, with_error_property
    ):
        self.authenticate(client)

        bmr = copy.deepcopy(self.valid_payload_with_iteration_error)
        if not with_error_property:
            # Either `error` or failed iteration mark a result as "errored",
            # see https://github.com/conbench/conbench/issues/813
            del bmr["error"]

        response = client.post(
            "/api/benchmarks/", json=self.valid_payload_with_iteration_error
        )
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id

        stats = self.valid_payload_with_iteration_error["stats"]
        stats["data"] = [float(x) if x is not None else None for x in stats["data"]]
        stats["times"] = [float(x) if x is not None else None for x in stats["times"]]

        self.assert_201_created(
            response, _expected_entity(benchmark_result, stats), location
        )

        assert (
            benchmark_result.error == self.valid_payload_with_iteration_error["error"]
        )

    def test_create_benchmark_with_one_iteration_no_error(self, client):
        self.authenticate(client)
        benchmark_data = self.valid_payload_with_iteration_error

        # remove the error to simulate only sending partial results
        benchmark_data.pop("error", None)

        response = client.post("/api/benchmarks/", json=benchmark_data)

        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)

        location = "http://localhost/api/benchmarks/%s/" % new_id
        stats = self.valid_payload_with_iteration_error["stats"]
        stats["data"] = [float(x) if x is not None else None for x in stats["data"]]
        stats["times"] = [float(x) if x is not None else None for x in stats["times"]]
        self.assert_201_created(
            response, _expected_entity(benchmark_result, stats), location
        )
        assert benchmark_result.error == {
            "status": "Partial result: not all iterations completed"
        }

    def test_create_benchmark_for_cluster_with_optional_info_changed(self, client):
        # Post benchmarks for cluster-1
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_for_cluster)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        hardware_id = benchmark_result.hardware.id
        hardware_hash = benchmark_result.hardware.hash

        # Post benchmarks for cluster-1 with different optional_info but the same cluster name and info
        payload = copy.deepcopy(self.valid_payload_for_cluster)
        payload["cluster_info"]["optional_info"] = {"field": 1}
        payload["run_id"] = _uuid()
        response = client.post("/api/benchmarks/", json=payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)

        # Confirm that a new hardware was created with new optional info...
        assert benchmark_result.hardware.id != hardware_id
        assert (
            benchmark_result.hardware.optional_info
            == payload["cluster_info"]["optional_info"]
        )

        # ...but the hash is the same since we didn't modify the cluster name or info
        assert benchmark_result.hardware.hash == hardware_hash

    def test_create_benchmark_for_cluster_with_info_changed(self, client):
        # Post benchmarks for cluster-1
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=self.valid_payload_for_cluster)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        hardware_id = benchmark_result.hardware.id

        # Post benchmarks for cluster-1 with different info but the same cluster name and optional_info
        payload = copy.deepcopy(self.valid_payload_for_cluster)
        payload["cluster_info"]["info"] = {"field": 1}
        payload["run_id"] = _uuid()
        response = client.post("/api/benchmarks/", json=payload)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.hardware.id != hardware_id
        assert benchmark_result.hardware.info == payload["cluster_info"]["info"]

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
        assert benchmark_result_1.hardware_id == benchmark_result_2.hardware_id
        assert benchmark_result_1.run_id != benchmark_result_2.run_id
        assert benchmark_result_1.commit_id == benchmark_result_2.commit_id

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
        del data["github"]["repository"]
        del data["machine_info"]["os_name"]
        data["machine_info"]["os_version"] = None
        data["stats"]["extra"] = "field"
        data["github"]["extra"] = "field"
        data["machine_info"]["extra"] = "field"
        response = client.post("/api/benchmarks/", json=data)
        message = {
            "github": {
                "extra": ["Unknown field."],
                "repository": ["Missing data for required field."],
            },
            "machine_info": {
                "extra": ["Unknown field."],
                "os_name": ["Missing data for required field."],
                "os_version": ["Field may not be null."],
            },
            "stats": {"extra": ["Unknown field."]},
        }
        self.assert_400_bad_request(response, message)

    def _assert_commit_repo_without_hash(self, response):
        assert response.status_code == 201, (response.status_code, response.text)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.commit is None
        assert (
            benchmark_result.commit_repo_url
            == self.valid_payload["github"]["repository"]
        )
        return benchmark_result, new_id

    def test_create_no_commit_hash(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"] = {"repository": data["github"]["repository"]}

        # create benchmark without commit context, with a repo
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_commit_repo_without_hash(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # create another benchmark without commit context, with a repo
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        benchmark_result, new_id = self._assert_commit_repo_without_hash(response)
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
        assert benchmark_result.commit.sha == "unknown commit"
        assert benchmark_result.commit.repository == ARROW_REPO
        assert benchmark_result.commit_repo_url == ARROW_REPO
        assert benchmark_result.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

        # create another benchmark with unknown commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        assert benchmark_result.commit.sha == "unknown commit"
        assert benchmark_result.commit.repository == ARROW_REPO
        assert benchmark_result.commit_repo_url == ARROW_REPO
        assert benchmark_result.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    def test_create_different_git_repo_format_at(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with git@g"
        data["github"]["repository"] = "git@github.com:apache/arrow"
        resp = client.post("/api/benchmarks/", json=data)
        assert resp.status_code == 201, resp.text
        print(resp.text)

        # In the future I don't think we want client tooling to send this.
        # Phase this out, remove complexity. See
        # https://github.com/conbench/conbench/pull/1134
        # assert resp.status_code == 400, resp.text
        # assert "must be a URL, starting with 'https://github.com'" in resp.text

    def test_create_repo_not_full_url(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with just org/repo"
        data["github"]["repository"] = "apache/arrow"

        resp = client.post("/api/benchmarks/", json=data)
        assert resp.status_code == 400, resp.text
        assert "must be a URL, starting with 'https://github.com'" in resp.text

    def test_create_allow_just_repo_empty_commit_hash(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = ARROW_REPO

        resp = client.post("/api/benchmarks/", json=data)
        assert resp.status_code == 400, resp.text
        assert "'commit' must be a non-empty string" in resp.text

    def test_create_only_commit_hash_no_repo_url(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "something something"
        data["github"]["repository"] = ""

        resp = client.post("/api/benchmarks/", json=data)
        assert resp.status_code == 400, resp.text
        assert "must be a URL, starting with 'https://github.com'" in resp.text

    @pytest.mark.parametrize("pr_number", [12345678, "12345678", None, "", "<absent>"])
    def test_create_allow_pr_number_variations(self, pr_number, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["pr_number"] = pr_number
        # In this test, `<absent>` is a sentinel for `pr_number` not being specified.
        # viable `github` submissions without `pr_number`:
        # - just `repository` (not a reproducible commit)
        # - just `repository` and `commit` (assumed to be on default branch)
        # - submit `branch` directly instead (mostly discouraged, but possible)
        if pr_number == "<absent>":
            data["github"].pop("pr_number")

        resp = client.post("/api/benchmarks/", json=data)
        assert resp.status_code == 201, resp.text

        new_id = resp.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(resp, _expected_entity(benchmark_result), location)

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

    def test_create_benchmark_context_missing(self, client):
        self.authenticate(client)
        payload = _fixtures.VALID_RESULT_PAYLOAD.copy()
        del payload["context"]
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 400, f"unexpected response: {resp.text}"
        assert '"context": ["Missing data for required field."]' in resp.text

    def test_create_benchmark_name_missing(self, client):
        self.authenticate(client)
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        del payload["tags"]["name"]
        # https://github.com/conbench/conbench/issues/935
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 400, resp.text
        assert "`name` property must be present in `tags" in resp.text

    @pytest.mark.parametrize(
        "tagdict",
        [
            # empty string key
            {"name": "foo", "": "foo"},
            # dict type value
            {"name": "foo", "foo": {"foo": "bar"}},
            # array type value
            {"name": "foo", "foo": ["foo"]},
        ],
    )
    def test_create_benchmark_bad_tags(self, client, tagdict):
        self.authenticate(client)
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        payload["tags"] = tagdict.copy()
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 400
        assert (
            "tags: bad value type for key" in resp.text
            or "tags: zero-length string as key is not allowed" in resp.text
        )

    # Context: see https://github.com/conbench/conbench/pull/948
    # we might want to apply more strictness in the future
    @pytest.mark.parametrize(
        "tagdict",
        [
            # Boolean value is currently allowed
            {"name": "foo", "key1": False},
            # Int value is currently allowed
            {"name": "foo", "key2": 1},
            # Float value is currently allowed
            {"name": "foo", "key3": 1.2},
            # non-empty string value is allowed
            {"name": "foo", "key4": "aa"},
            # empty string value is currently allowed (accepted, but dropped)
            {"name": "foo", "key5": ""},
            # None value is currently allowed (accepted, but dropped)
            {"name": "foo", "key6": None},
        ],
    )
    def test_create_benchmark_good_tags(self, client, tagdict):
        self.authenticate(client)
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        payload["tags"] = tagdict.copy()
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 201
        assert resp.json["tags"]
        assert "key5" not in resp.json["tags"]
        assert "key6" not in resp.json["tags"]

    def test_create_benchmark_context_empty(self, client):
        """
        It is an error to provide no context object (see test above). Whether
        an empty context object is something we want to accept is debatable. As
        part of working on https://github.com/conbench/conbench/issues/365 we
        for now opt for accepting it, i.e. HTML template rendering must expect
        this scenario.
        """
        self.authenticate(client)
        payload = _fixtures.VALID_RESULT_PAYLOAD.copy()
        payload["run_id"] = _uuid()
        payload["batch_id"] = _uuid()

        payload["context"] = {}
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 201, f"unexpected response: {resp.text}"

        benchmark_result_id = resp.json["id"]
        # Confirm that an empty context was created.
        context_url = resp.json["links"]["context"]
        resp = client.get(context_url)
        assert resp.status_code == 200, f"unexpected response: {resp.text}"

        # expected keys: 'id', 'links' -- no more keys: empty context
        assert set(resp.json.keys()) == set(["id", "links"])
        context_id = resp.json["id"]

        # Test benchmark HTML template renderer with above-created benchmark
        # object. There was a time when the benchmark-entity template failed
        # rendering for empty contexts, see
        # https://github.com/conbench/conbench/issues/365
        resp = client.get(f"/benchmark-results/{benchmark_result_id}/")
        assert resp.status_code == 200, f"unexpected response: {resp.text}"

        # As of today the rendered view shows the context ID. Confirm that. In
        # the future it might be reasonable to not show the context ID, but
        # maybe only a helpful placeholder such as "empty context".
        assert context_id in resp.text

    @pytest.mark.parametrize(
        "timeinput, timeoutput",
        [
            ("2023-11-25 21:02:41", "2023-11-25T21:02:41Z"),
            ("2023-11-25 22:02:36Z", "2023-11-25T22:02:36Z"),
            ("2023-11-25T22:02:36Z", "2023-11-25T22:02:36Z"),
            # That next pair confirms timezone conversion.
            ("2023-11-25 23:02:00+07:00", "2023-11-25T16:02:00Z"),
            # Confirm that fractions of seconds can be provided, but are not
            # returned (we can dispute that of course).
            ("2023-11-25T22:02:36.123456Z", "2023-11-25T22:02:36Z"),
        ],
    )
    def test_create_benchmark_timestamp_timezone(self, client, timeinput, timeoutput):
        self.authenticate(client)

        d = self.valid_payload.copy()
        d["timestamp"] = timeinput
        resp = client.post("/api/benchmarks/", json=d)
        assert resp.status_code == 201, resp.text
        bid = resp.json["id"]

        resp = client.get(f"/api/benchmarks/{bid}/")
        assert resp.status_code == 200, resp.text

        assert resp.json["timestamp"] == timeoutput

    def test_create_result_missing_stats_and_error(self, client):
        self.authenticate(client)
        result = _fixtures.VALID_RESULT_PAYLOAD.copy()
        del result["stats"]
        try:
            del result["error"]
        except KeyError:
            # if it wasn't set before, that's good, too.
            pass

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 400, resp.text

        # This is currently the error message emitted by marshmallow
        # schema validation.
        assert "Either stats or error field is required" in resp.text

    @pytest.mark.parametrize(
        "samples",
        [(1,), (3, 5), (3, 5, 7)],
    )
    def test_create_result_no_agg_before_three(self, client, samples):
        self.authenticate(client)

        aggkeys = ("q1", "q3", "median", "min", "max", "stdev", "iqr")

        result = _fixtures.VALID_RESULT_PAYLOAD.copy()
        result["stats"] = {
            "data": samples,
            "unit": "s",
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 201, resp.text

        # Mean must be defined for all non-errored results, i.e. also when
        # there is just one data point in the result.
        # See https://github.com/conbench/conbench/issues/1169
        assert resp.json["stats"]["mean"] > 0

        # prepare for testing
        # https://github.com/conbench/conbench/issues/1118
        if len(samples) >= 3:
            for k in aggkeys:
                assert resp.json["stats"][k] > 0
        else:
            for k in aggkeys:
                assert resp.json["stats"][k] is None

    @pytest.mark.parametrize(
        "samples",
        [(1,), (3, 5), (3, 5, 7)],
    )
    @pytest.mark.parametrize(
        "uekey",
        ["iqr", "q1", "q3", "median", "stdev"],
    )
    def test_create_result_unexpected_stats_keys(self, client, uekey, samples):
        self.authenticate(client)

        result = _fixtures.VALID_RESULT_PAYLOAD.copy()
        result["stats"] = {
            "data": samples,
            "unit": "s",
            # Set some bogus aggregate.
            uekey: 3,
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 201, resp.text
        bmrid = resp.json["id"]

        resp = client.get(f"/api/benchmark-results/{bmrid}/")
        assert resp.status_code == 200, resp.text

        bmrdict = resp.json

        if len(samples) < 3:
            # "be liberal in what you accept"; confirm that information has
            # been dropped (was not put into the database): for example,
            # when stddev is provided for two samples then it's not stored,
            # and not returned
            assert bmrdict["stats"][uekey] is None

    def test_create_result_bad_unit(self, client):
        self.authenticate(client)
        result = _fixtures.VALID_RESULT_PAYLOAD.copy()

        result["stats"] = {
            "data": (3, 5),
            "unit": "kg",
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 400, resp.text
        assert "invalid unit string `kg`" in resp.text

    def test_special_unit_b_s(self, client):
        self.authenticate(client)
        result = _fixtures.VALID_RESULT_PAYLOAD.copy()

        result["stats"] = {
            "data": (3, 5),
            "unit": "b/s",  # means B/s, is rewritten
        }

        resp = client.post("/api/benchmark-results/", json=result)
        assert resp.status_code == 201, resp.text
        assert resp.json["stats"]["unit"] == "B/s", resp.json
