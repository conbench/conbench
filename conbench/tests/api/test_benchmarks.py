import copy
import decimal

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.distribution import Distribution
from ...entities.summary import Summary
from ...runner import Conbench
from ...tests.api import _asserts
from ...tests.api import _fixtures
from ...tests.helpers import _uuid


def _expected_entity(summary):
    return _api_benchmark_entity(
        summary.id,
        summary.context_id,
        summary.case.id,
        summary.batch_id,
        summary.run_id,
        summary.case.name,
    )


def create_benchmark_summary(
    name=None, batch_id=None, run_id=None, results=None, unit=None, sha=None
):
    data = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    if name:
        data["tags"]["name"] = name
    if batch_id:
        data["stats"]["batch_id"] = batch_id
    if run_id:
        data["stats"]["run_id"] = run_id
    if sha:
        data["github"]["commit"] = sha

    if results is not None:
        unit = unit if unit else "s"
        run_id = data["stats"]["run_id"]
        run_name = data["stats"]["run_name"]
        batch_id = data["stats"]["batch_id"]
        timestamp = data["stats"]["timestamp"]
        data["stats"] = Conbench._stats(
            results, unit, [], "s", timestamp, run_id, batch_id, run_name
        )

    summary = Summary.create(data)
    return summary


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/api/benchmarks/{}/"
    public = True

    def _create(self, name=None, run_id=None, results=None, unit=None, sha=None):
        return create_benchmark_summary(
            name=name, run_id=run_id, results=results, unit=unit, sha=sha
        )

    def test_get_benchmark(self, client):
        self.authenticate(client)
        summary = self._create()
        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, _expected_entity(summary))

    def test_get_benchmark_regression(self, client):
        self.authenticate(client)

        name, run_0, run_1, run_2 = _uuid(), _uuid(), _uuid(), _uuid()

        # create a distribution history & a regression
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[0],
            unit="i/s",
            run_id=run_0,
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[1],
            unit="i/s",
            run_id=run_1,
            sha=_fixtures.PARENT,
        )
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="i/s",
            run_id=run_2,
        )

        expected = _expected_entity(summary)
        expected["stats"].update(
            {
                "data": ["1.000000", "2.000000", "3.000000"],
                "iqr": "1.000000",
                "iterations": 3,
                "max": "3.000000",
                "mean": "2.000000",
                "median": "2.000000",
                "min": "1.000000",
                "q1": "1.500000",
                "q3": "2.500000",
                "stdev": "1.000000",
                "times": [],
                "z_score": "-{:.6f}".format(abs(_fixtures.Z_SCORE_DOWN)),
                "z_regression": True,
                "unit": "i/s",
            }
        )

        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_regression_less_is_better(self, client):
        self.authenticate(client)

        name, run_0, run_1, run_2 = _uuid(), _uuid(), _uuid(), _uuid()

        # create a distribution history & a regression
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            unit="s",
            run_id=run_0,
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            unit="s",
            run_id=run_1,
            sha=_fixtures.PARENT,
        )
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="s",
            run_id=run_2,
        )

        expected = _expected_entity(summary)
        expected["stats"].update(
            {
                "data": ["10.000000", "20.000000", "30.000000"],
                "iqr": "10.000000",
                "iterations": 3,
                "max": "30.000000",
                "mean": "20.000000",
                "median": "20.000000",
                "min": "10.000000",
                "q1": "15.000000",
                "q3": "25.000000",
                "stdev": "10.000000",
                "times": [],
                "z_score": "-{:.6f}".format(abs(_fixtures.Z_SCORE_UP)),
                "z_regression": True,
            }
        )

        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_improvement(self, client):
        self.authenticate(client)

        name, run_0, run_1, run_2 = _uuid(), _uuid(), _uuid(), _uuid()

        # create a distribution history & a improvement
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[0],
            unit="i/s",
            run_id=run_0,
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_UP[1],
            unit="i/s",
            run_id=run_1,
            sha=_fixtures.PARENT,
        )
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="i/s",
            run_id=run_2,
        )

        expected = _expected_entity(summary)
        expected["stats"].update(
            {
                "data": ["10.000000", "20.000000", "30.000000"],
                "iqr": "10.000000",
                "iterations": 3,
                "max": "30.000000",
                "mean": "20.000000",
                "median": "20.000000",
                "min": "10.000000",
                "q1": "15.000000",
                "q3": "25.000000",
                "stdev": "10.000000",
                "times": [],
                "z_score": "{:.6f}".format(abs(_fixtures.Z_SCORE_UP)),
                "z_improvement": True,
                "unit": "i/s",
            }
        )

        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, expected)

    def test_get_benchmark_improvement_less_is_better(self, client):
        self.authenticate(client)

        name, run_0, run_1, run_2 = _uuid(), _uuid(), _uuid(), _uuid()

        # create a distribution history & a improvement
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[0],
            unit="s",
            run_id=run_0,
            sha=_fixtures.GRANDPARENT,
        )
        self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[1],
            unit="s",
            run_id=run_1,
            sha=_fixtures.PARENT,
        )
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="s",
            run_id=run_2,
        )

        expected = _expected_entity(summary)
        expected["stats"].update(
            {
                "data": ["1.000000", "2.000000", "3.000000"],
                "iqr": "1.000000",
                "iterations": 3,
                "max": "3.000000",
                "mean": "2.000000",
                "median": "2.000000",
                "min": "1.000000",
                "q1": "1.500000",
                "q3": "2.500000",
                "stdev": "1.000000",
                "times": [],
                "z_score": "{:.6f}".format(abs(_fixtures.Z_SCORE_DOWN)),
                "z_improvement": True,
            }
        )

        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, expected)


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
    required_fields = ["machine_info", "stats", "tags", "context", "github"]
    valid_payload = _fixtures.VALID_PAYLOAD

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
        assert summary_1.run.machine_id == summary_2.run.machine_id
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
        data["tags"]["name"] = _uuid()

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
        assert summary_1.run.machine_id == summary_2.run.machine_id
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
