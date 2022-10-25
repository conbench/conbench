import copy

import pytest

from ...entities.benchmark_result import BenchmarkFacadeSchema
from ...tests.api import _fixtures
from ...tests.helpers import _uuid
from ._example_benchmarks import (
    CasesBenchmark,
    ExternalBenchmark,
    SimpleBenchmark,
    SimpleBenchmarkThatFails,
    SimpleBenchmarkWithClusterInfo,
)

EXAMPLE = copy.deepcopy(_fixtures.VALID_PAYLOAD)
EXAMPLE_WITH_CLUSTER_INFO = copy.deepcopy(_fixtures.VALID_PAYLOAD_FOR_CLUSTER)
EXAMPLE_WITH_ERROR = copy.deepcopy(_fixtures.VALID_PAYLOAD_WITH_ERROR)
for example in [EXAMPLE, EXAMPLE_WITH_CLUSTER_INFO, EXAMPLE_WITH_ERROR]:
    example.pop("run_name")
    example.pop("run_reason")
    example.pop("validation")
    example["info"] = {
        "benchmark_language_version": "Python 3.8.5",
    }
    example["context"] = {
        "benchmark_language": "Python",
    }


def assert_keys_equal(a, b):
    assert set(a.keys()) == set(b.keys())


def assert_repo_is_valid(repo):
    assert repo.startswith("https://github.com/") or repo.startswith("git@github.com:")
    assert repo.endswith("/conbench")


def test_runner_simple_benchmark():
    for benchmark_class, payload_example, hardware_type, tag in [
        (SimpleBenchmark, EXAMPLE, "machine", "addition"),
        (
            SimpleBenchmarkWithClusterInfo,
            EXAMPLE_WITH_CLUSTER_INFO,
            "cluster",
            "product",
        ),
    ]:
        benchmark = benchmark_class()
        [(result, output)] = benchmark.run(iterations=10)
        assert not BenchmarkFacadeSchema.create.validate(result)
        expected_tags = {"name": tag}
        assert output == 2
        assert_keys_equal(result, payload_example)
        assert_keys_equal(result["tags"], expected_tags)
        assert_keys_equal(result["stats"], payload_example["stats"])
        assert_keys_equal(result["info"], payload_example["info"])
        assert_keys_equal(result["context"], payload_example["context"])
        assert_keys_equal(result["github"], payload_example["github"])
        assert_keys_equal(
            result[f"{hardware_type}_info"], payload_example[f"{hardware_type}_info"]
        )
        assert result["tags"] == expected_tags
        assert result["stats"]["iterations"] == 10
        assert len(result["stats"]["data"]) == 10
        assert result["context"]["benchmark_language"] == "Python"
        assert_repo_is_valid(result["github"]["repository"])


def test_runner_simple_benchmark_that_fails():
    benchmark = SimpleBenchmarkThatFails()
    tag = "division-with-failure"

    with pytest.raises(ZeroDivisionError):
        [(_, _)] = benchmark.run(iterations=10)

    result = benchmark.conbench.published_benchmark
    assert not BenchmarkFacadeSchema.create.validate(result)
    print(result)
    assert_keys_equal(result, EXAMPLE_WITH_ERROR)
    for key in ["info", "context", "github", "machine_info"]:
        assert_keys_equal(result[key], EXAMPLE_WITH_ERROR[key])
    assert result["tags"] == {"name": tag}
    assert result["context"]["benchmark_language"] == "Python"
    assert_repo_is_valid(result["github"]["repository"])
    assert "stats" not in result
    assert "stack_trace" in result["error"]
    for text in [
        "Traceback (most recent call last):",
        "data, output = self._get_timing(f, iterations, timing_options)",
        "in _get_timing",
        "output = f()",
        "tests/benchmark/_example_benchmarks.py",
        "return lambda: 1 / 0",
        "ZeroDivisionError: division by zero",
    ]:
        assert text in result["error"]["stack_trace"]


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
    assert_keys_equal(result["info"], EXAMPLE["info"])
    assert_keys_equal(result["context"], EXAMPLE["context"])
    assert_keys_equal(result["github"], EXAMPLE["github"])
    assert_keys_equal(result["machine_info"], EXAMPLE["machine_info"])
    assert result["tags"] == expected_tags
    assert result["stats"]["iterations"] == 10
    assert len(result["stats"]["data"]) == 10
    assert result["context"]["benchmark_language"] == "Python"
    assert_repo_is_valid(result["github"]["repository"])


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
    assert_repo_is_valid(result["github"]["repository"])


def test_runner_can_specify_run_and_batch_id():
    benchmark = SimpleBenchmark()
    run_id, batch_id = _uuid(), _uuid()
    [(result, output)] = benchmark.run(run_id=run_id, batch_id=batch_id)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["run_id"] == run_id
    assert result["batch_id"] == batch_id


def test_runner_can_omit_run_and_batch_id():
    benchmark = SimpleBenchmark()
    [(result, output)] = benchmark.run()
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["run_id"] is not None
    assert result["batch_id"] is not None


def test_runner_null_run_and_batch_id():
    benchmark = SimpleBenchmark()
    [(result, output)] = benchmark.run(run_id=None, batch_id=None)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["run_id"] is not None
    assert result["batch_id"] is not None


def test_runner_omit_batch_id():
    benchmark = SimpleBenchmark()
    run_id = _uuid()
    [(result, output)] = benchmark.run(run_id=run_id)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["run_id"] == run_id
    assert result["batch_id"] is not None


def test_runner_null_batch_id():
    benchmark = SimpleBenchmark()
    run_id = _uuid()
    [(result, output)] = benchmark.run(run_id=run_id, batch_id=None)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["run_id"] == run_id
    assert result["batch_id"] is not None


def test_runner_omit_run_id():
    benchmark = SimpleBenchmark()
    batch_id = _uuid()
    [(result, output)] = benchmark.run(batch_id=batch_id)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["batch_id"] == batch_id
    assert result["run_id"] is not None


def test_runner_null_run_id():
    benchmark = SimpleBenchmark()
    batch_id = _uuid()
    [(result, output)] = benchmark.run(batch_id=batch_id, run_id=None)
    assert not BenchmarkFacadeSchema.create.validate(result)
    assert output == 2
    assert result["batch_id"] == batch_id
    assert result["run_id"] is not None
