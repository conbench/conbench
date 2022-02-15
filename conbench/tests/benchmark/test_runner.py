import copy

from ...entities.summary import BenchmarkFacadeSchema
from ...tests.api import _fixtures
from ...tests.helpers import _uuid
from ._example_benchmarks import (
    CasesBenchmark,
    ExternalBenchmark,
    SimpleBenchmark,
    SimpleBenchmarkWithClusterInfo,
)

REPO = "https://github.com/conbench/conbench"
EXAMPLE = copy.deepcopy(_fixtures.VALID_PAYLOAD)
EXAMPLE_WITH_CLUSTER_INFO = copy.deepcopy(_fixtures.VALID_PAYLOAD_FOR_CLUSTER)
for example in [EXAMPLE, EXAMPLE_WITH_CLUSTER_INFO]:
    example.pop("run_name")
    example["info"] = {
        "benchmark_language_version": "Python 3.8.5",
    }
    example["context"] = {
        "benchmark_language": "Python",
    }


def assert_keys_equal(a, b):
    assert set(a.keys()) == set(b.keys())


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
        print(benchmark)
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
    assert_keys_equal(result["info"], EXAMPLE["info"])
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
