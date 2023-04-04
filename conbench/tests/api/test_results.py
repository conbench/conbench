import copy

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.benchmark_result import BenchmarkResult
from ...entities.run import Run
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

ARROW_REPO = "https://github.com/apache/arrow"
CONBENCH_REPO = "https://github.com/conbench/conbench"


def _expected_entity(benchmark_result: BenchmarkResult, stats=None):
    return _api_benchmark_entity(
        benchmark_result.id,
        benchmark_result.info_id,
        benchmark_result.context_id,
        benchmark_result.batch_id,
        benchmark_result.run_id,
        benchmark_result.case.name,
        stats,
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
                "z_score": None,
                "z_regression": False,
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
                "z_score": None,
                "z_regression": False,
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
                "z_score": None,
                "z_improvement": False,
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
                "z_score": None,
                "z_improvement": False,
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
    valid_payload_with_iteration_error = _fixtures.VALID_PAYLOAD_WITH_ITERATION_ERROR
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

    def test_create_benchmark_after_run_different_machine_info(self, client):
        """
        This test documents current behavior that I was initially only
        suspecting and then wanted to confirm with code.

        We can of course re-think the specification (expected behavior).

        This is a special case in the API surface, but because it's API
        behavior it's important that we think about specification first
        (desired behavior), and then judge about the implementation.

        I think this is an artifact of us allowing for potentially many
        concurrent executors to submit results within a specific run without
        requiring special coordination between those executors. That is, it is
        expected that the submitted run metadata (like name and machine info)
        are equivalent across all BenchmarkResult entities, and the fastest
        submitter wins the price of DB insertion, while the other racers get
        their info silently dropped.
        """

        def assert_machine_info_equals_hardware(hwdict, midict):
            # Add 'type' key to machine_info dict, and intify all values
            # that allow for doing so.
            cmp = {"type": "machine"}
            for k, v in midict.items():
                try:
                    cmp[k] = int(v)
                except (TypeError, ValueError):
                    cmp[k] = v

            # Remove id from hardware dict.
            ref = hwdict.copy()
            del ref["id"]

            # Compare (processed) machine info to reference
            assert ref == cmp

        self.authenticate(client)

        machine_info_A = _fixtures.MACHINE_INFO.copy()
        run_payload = _fixtures.VALID_RUN_PAYLOAD.copy()
        run_payload["machine_info"] = machine_info_A
        resp = client.post("/api/runs/", json=run_payload)
        assert resp.status_code == 201, resp.text

        # Read back Run details from API.
        resp = client.get(f"/api/runs/{run_payload['id']}/")
        assert resp.status_code == 200, resp.text
        run_asindb = resp.json

        # Confirm that the above's Run submission created a Hardware entity
        # representing the details in `machine_info_A`.
        assert_machine_info_equals_hardware(run_asindb["hardware"], machine_info_A)

        # Create a copy of the above's machine_info example object with a
        # different CPU model name. This is set in
        # BenchmarkResultCreate.machine_info.cpu_model_name and will be
        # silently dropped
        lost_cpu_model_name = "qubit1337"
        machine_info_B = _fixtures.MACHINE_INFO.copy()
        machine_info_B["cpu_model_name"] = lost_cpu_model_name

        # Submit BenchmarkResultCreate structure, refer to the previously
        # submitted Run entity (via ID), but provide _different_ machine_info.
        bmresult_payload = self.valid_payload.copy()
        bmresult_payload["run_id"] = run_payload["id"]
        bmresult_payload["machine_info"] = machine_info_B
        resp = client.post("/api/benchmarks/", json=bmresult_payload)
        assert resp.status_code == 201, resp.text
        bid = resp.json["id"]

        # Read back BenchmarkResult details from API.
        resp = client.get(f"/api/benchmarks/{bid}/")
        assert resp.status_code == 200, resp.text
        bm_asindb = resp.json
        # Confirm that this benchmark result is associated with the above's run
        # entity.
        assert bm_asindb["run_id"] == run_asindb["id"]

        # Read back Run details again from API.
        resp = client.get(f"/api/runs/{run_payload['id']}/")
        assert resp.status_code == 200, resp.text
        run_asindb2 = resp.json
        # Confirm that machine_info_A took precedence.
        assert_machine_info_equals_hardware(run_asindb2["hardware"], machine_info_A)

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

    def test_create_benchmark_with_one_iteration_error(self, client):
        self.authenticate(client)
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

        # new code path: no context, not unknown context
        # assert benchmark_result.run.commit.repository == ARROW_REPO
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
        # new code path: no context, not unknown context
        # assert benchmark_result.run.commit.repository == CONBENCH_REPO
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
        # new code path: no context, not unknown context
        # assert benchmark_result.run.commit.sha == "something something"
        assert benchmark_result.run.commit.repository == ""
        assert benchmark_result.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

    @pytest.mark.parametrize("pr_number", [12345678, "12345678", None, "", "<absent>"])
    def test_create_allow_pr_number_variations(self, pr_number, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["pr_number"] = pr_number
        # `<absent>` is a sentinel for `pr_number` not being specified.
        # viable `github` submissions without `pr_number`:
        # - just `repository` and `commit` (assumed to be on default branch)
        # - submit `branch` directly instead (mostly discouraged, but possible)
        if pr_number == "<absent>":
            data["github"].pop("pr_number")

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        benchmark_result = BenchmarkResult.one(id=new_id)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(benchmark_result), location)

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
        payload = _fixtures.VALID_PAYLOAD.copy()
        del payload["context"]
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 400, f"unexpected response: {resp.text}"
        assert '"context": ["Missing data for required field."]' in resp.text

    def test_create_benchmark_name_missing(self, client):
        self.authenticate(client)
        payload = copy.deepcopy(_fixtures.VALID_PAYLOAD)
        del payload["tags"]["name"]
        with pytest.raises(KeyError):
            client.post(self.url, json=payload)
            # TODO: https://github.com/conbench/conbench/issues/935
            # This here just quickly checks that there is a failure at all,
            # that 'name' is required.

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
        payload = copy.deepcopy(_fixtures.VALID_PAYLOAD)
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
        payload = copy.deepcopy(_fixtures.VALID_PAYLOAD)
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
        payload = _fixtures.VALID_PAYLOAD.copy()
        payload["run_id"] = _uuid()
        payload["batch_id"] = _uuid()

        payload["context"] = {}
        resp = client.post(self.url, json=payload)
        assert resp.status_code == 201, f"unexpected response: {resp.text}"

        benchmark_id = resp.json["id"]
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
        resp = client.get(f"/benchmark-results/{benchmark_id}/")
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
