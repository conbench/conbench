import copy

from ...entities.summary import BenchmarkFacadeSchema
from ...tests.api import _fixtures
from ._example_benchmarks import CasesBenchmark, ExternalBenchmark, SimpleBenchmark

REPO = "https://github.com/ursacomputing/conbench"
EXAMPLE = copy.deepcopy(_fixtures.VALID_PAYLOAD)
EXAMPLE.pop("run_name")
EXAMPLE["context"] = {
    "benchmark_language_version": "Python 3.8.5",
    "benchmark_language": "Python",
}


def assert_keys_equal(a, b):
    assert set(a.keys()) == set(b.keys())


def test_runner_simple_benchmark():
    benchmark = SimpleBenchmark()
    [(result, output)] = benchmark.run(iterations=10)
    assert not BenchmarkFacadeSchema.create.validate(result)
    expected_tags = {"name": "addition"}
    assert output == 2
    assert_keys_equal(result, EXAMPLE)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], EXAMPLE["stats"])
    assert_keys_equal(result["context"], EXAMPLE["context"])
    assert_keys_equal(result["github"], EXAMPLE["github"])
    assert_keys_equal(result["machine_info"], EXAMPLE["machine_info"])
    assert result["tags"] == expected_tags
    assert result["stats"]["iterations"] == 10
    assert len(result["stats"]["data"]) == 10
    assert result["context"]["benchmark_language"] == "Python"
    assert result["github"]["repository"] == REPO


def test_runner_case_benchmark():
    benchmark = CasesBenchmark()
    case = ("2", "10")
    [(result, output)] = benchmark.run(case=case, iterations=10)
    assert not BenchmarkFacadeSchema.create.validate(result)
    expected_tags = {"name": "matrix", "rows": "2", "columns": "10"}
    assert output == [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ]
    assert_keys_equal(result, EXAMPLE)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], EXAMPLE["stats"])
    assert_keys_equal(result["context"], EXAMPLE["context"])
    assert_keys_equal(result["github"], EXAMPLE["github"])
    assert_keys_equal(result["machine_info"], EXAMPLE["machine_info"])
    assert result["tags"] == expected_tags
    assert result["stats"]["iterations"] == 10
    assert len(result["stats"]["data"]) == 10
    assert result["context"]["benchmark_language"] == "Python"
    assert result["github"]["repository"] == REPO


def test_runner_external_benchmark():
    benchmark = ExternalBenchmark()
    [(result, output)] = benchmark.run()
    assert not BenchmarkFacadeSchema.create.validate(result)
    expected_tags = {"name": "external"}
    assert output == {
        "data": [100, 200, 300],
        "unit": "i/s",
        "times": [0.1, 0.2, 0.3],
        "time_unit": "s",
    }
    assert_keys_equal(result, EXAMPLE)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], EXAMPLE["stats"])
    assert_keys_equal(result["github"], EXAMPLE["github"])
    assert_keys_equal(result["machine_info"], EXAMPLE["machine_info"])
    assert result["tags"] == expected_tags
    assert result["stats"]["iterations"] == 3
    assert len(result["stats"]["data"]) == 3
    assert result["context"] == {"benchmark_language": "C++"}
    assert result["github"]["repository"] == REPO
