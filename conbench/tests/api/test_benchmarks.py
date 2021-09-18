import copy
import decimal

import pytest

from ...api._examples import _api_benchmark_entity
from ...entities._entity import NotFound
from ...entities.distribution import Distribution
from ...entities.summary import Summary
from ...tests.api import _asserts, _fixtures
from ...tests.helpers import _uuid

ARROW_REPO = "https://github.com/apache/arrow"
CONBENCH_REPO = "https://github.com/conbench/conbench"


def _expected_entity(summary):
    return _api_benchmark_entity(
        summary.id,
        summary.context_id,
        summary.case.id,
        summary.batch_id,
        summary.run_id,
        summary.case.name,
    )


class TestBenchmarkGet(_asserts.GetEnforcer):
    url = "/api/benchmarks/{}/"
    public = True

    def _create(self, name=None, results=None, unit=None, sha=None):
        return _fixtures.summary(
            name=name,
            results=results,
            unit=unit,
            sha=sha,
        )

    def test_get_benchmark(self, client):
        self.authenticate(client)
        summary = self._create()
        response = client.get(f"/api/benchmarks/{summary.id}/")
        self.assert_200_ok(response, _expected_entity(summary))

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
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="i/s",
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
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="s",
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
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_UP[2],
            unit="i/s",
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
        summary = self._create(
            name=name,
            results=_fixtures.RESULTS_DOWN[2],
            unit="s",
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
        summary = _fixtures.summary()

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
        summary = _fixtures.summary()
        response = client.get("/api/benchmarks/")
        self.assert_200_ok(response, contains=_expected_entity(summary))

    def test_benchmark_list_filter_by_name(self, client):
        self.authenticate(client)
        _fixtures.summary(name="aaa")
        summary = _fixtures.summary(name="bbb")
        _fixtures.summary(name="ccc")
        response = client.get("/api/benchmarks/?name=bbb")
        self.assert_200_ok(response, [_expected_entity(summary)])

    def test_benchmark_list_filter_by_batch_id(self, client):
        self.authenticate(client)
        _fixtures.summary(batch_id="10")
        summary = _fixtures.summary(batch_id="20")
        _fixtures.summary(batch_id="30")
        response = client.get("/api/benchmarks/?batch_id=20")
        self.assert_200_ok(response, [_expected_entity(summary)])

    def test_benchmark_list_filter_by_run_id(self, client):
        self.authenticate(client)
        _fixtures.summary(run_id="100")
        summary = _fixtures.summary(run_id="200")
        _fixtures.summary(run_id="300")
        response = client.get("/api/benchmarks/?run_id=200")
        self.assert_200_ok(response, [_expected_entity(summary)])


class TestBenchmarkPost(_asserts.PostEnforcer):
    url = "/api/benchmarks/"
    valid_payload = _fixtures.VALID_PAYLOAD
    required_fields = [
        "run_id",
        "batch_id",
        "timestamp",
        "machine_info",
        "stats",
        "tags",
        "context",
    ]

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
        data["run_id"] = data["run_id"] + "_X"
        response = client.post("/api/benchmarks/", json=data)
        summary_2 = Summary.one(id=response.json["id"])
        assert summary_1.id != summary_2.id
        assert summary_1.case_id == summary_2.case_id
        assert summary_1.context_id == summary_2.context_id
        assert summary_1.run.machine_id == summary_2.run.machine_id
        assert summary_1.run_id != summary_2.run_id
        assert summary_1.run.commit_id == summary_2.run.commit_id

    def test_create_benchmark_can_specify_run_and_batch_id(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        run_id, batch_id = _uuid(), _uuid()
        data["run_id"] = run_id
        data["batch_id"] = batch_id
        response = client.post("/api/benchmarks/", json=data)
        summary = Summary.one(id=response.json["id"])
        assert summary.run_id == run_id
        assert summary.batch_id == batch_id

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
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == ""
        assert summary.run.commit.repository == ""
        assert summary.run.commit.parent is None
        return summary, new_id

    def test_create_no_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        del data["github"]

        # create benchmark without commit context
        response = client.post("/api/benchmarks/", json=data)
        summary, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

        # create another benchmark without commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        summary, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_empty_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = ""

        # create benchmark without commit context
        response = client.post("/api/benchmarks/", json=data)
        summary, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

        # create another benchmark without commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        summary, new_id = self._assert_none_commit(response)
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_unknown_commit_context(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "unknown commit"
        data["github"]["repository"] = ARROW_REPO

        # create benchmark with unknown commit context
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == "unknown commit"
        assert summary.run.commit.repository == ARROW_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

        # create another benchmark with unknown commit context
        # (test duplicate key duplicate key -- commit_index)
        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == "unknown commit"
        assert summary.run.commit.repository == ARROW_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_different_git_repo_format(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with git@g"
        data["github"]["repository"] = "git@github.com:apache/arrow"

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == "testing repository with git@g"
        assert summary.run.commit.repository == ARROW_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_repo_not_full_url(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "testing repository with just org/repo"
        data["github"]["repository"] = "apache/arrow"

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == "testing repository with just org/repo"
        assert summary.run.commit.repository == ARROW_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_allow_just_repository(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = ARROW_REPO

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == ""
        assert summary.run.commit.repository == ARROW_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

        # And again with a different repository with an empty sha
        data["run_id"] = _uuid()
        data["github"]["commit"] = ""
        data["github"]["repository"] = CONBENCH_REPO

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == ""
        assert summary.run.commit.repository == CONBENCH_REPO
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

    def test_create_allow_just_sha(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["run_id"] = _uuid()
        data["github"]["commit"] = "something something"
        data["github"]["repository"] = ""

        response = client.post("/api/benchmarks/", json=data)
        new_id = response.json["id"]
        summary = Summary.one(id=new_id)
        assert summary.run.commit.sha == "something something"
        assert summary.run.commit.repository == ""
        assert summary.run.commit.parent is None
        location = "http://localhost/api/benchmarks/%s/" % new_id
        self.assert_201_created(response, _expected_entity(summary), location)

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
        distributions = Distribution.all(case_id=case_id)
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
        distributions = Distribution.all(case_id=case_id)
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
