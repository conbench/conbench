from ._example_benchmarks import CasesBenchmark, ExternalBenchmark, SimpleBenchmark
from ...entities.summary import BenchmarkFacadeSchema


REPO = "https://github.com/ursacomputing/conbench"
example = {
    "run_id": "b00966bd99a94c34abc7a042b7a0a5b4",
    "batch_id": "307182bb124544c794a2e38b5e7fd24a",
    "timestamp": "2020-12-16T03:40:29.819878+00:00",
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.8.5",
    },
    "github": {
        "commit": "478286658055bb91737394c2065b92a7e92fb0c1",
        "repository": "https://github.com/apache/arrow",
    },
    "machine_info": {
        "architecture_name": "x86_64",
        "cpu_core_count": "2",
        "cpu_frequency_max_hz": "3500000000",
        "cpu_l1d_cache_bytes": "32768",
        "cpu_l1i_cache_bytes": "32768",
        "cpu_l2_cache_bytes": "262144",
        "cpu_l3_cache_bytes": "4194304",
        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
        "cpu_thread_count": "4",
        "kernel_name": "19.6.0",
        "memory_bytes": "17179869184",
        "name": "machine-abc",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "data": [
            "0.000002",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
        ],
        "times": [
            "0.000002",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
            "0.000000",
            "0.000001",
        ],
        "unit": "s",
        "time_unit": "s",
        "iqr": "0.000001",
        "iterations": 10,
        "max": "0.000002",
        "mean": "0.000001",
        "median": "0.000001",
        "min": "0.000000",
        "q1": "0.000000",
        "q3": "0.000001",
        "stdev": "0.000001",
    },
    "tags": {
        "name": "addition",
    },
}


def assert_keys_equal(a, b):
    assert set(a.keys()) == set(b.keys())


def test_runner_simple_benchmark():
    benchmark = SimpleBenchmark()
    [(result, output)] = benchmark.run(iterations=10)
    assert not BenchmarkFacadeSchema.create.validate(result)
    expected_tags = {"name": "addition"}
    assert output == 2
    assert_keys_equal(result, example)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], example["stats"])
    assert_keys_equal(result["context"], example["context"])
    assert_keys_equal(result["github"], example["github"])
    assert_keys_equal(result["machine_info"], example["machine_info"])
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
    assert_keys_equal(result, example)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], example["stats"])
    assert_keys_equal(result["context"], example["context"])
    assert_keys_equal(result["github"], example["github"])
    assert_keys_equal(result["machine_info"], example["machine_info"])
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
    assert_keys_equal(result, example)
    assert_keys_equal(result["tags"], expected_tags)
    assert_keys_equal(result["stats"], example["stats"])
    assert_keys_equal(result["github"], example["github"])
    assert_keys_equal(result["machine_info"], example["machine_info"])
    assert result["tags"] == expected_tags
    assert result["stats"]["iterations"] == 3
    assert len(result["stats"]["data"]) == 3
    assert result["context"] == {"benchmark_language": "C++"}
    assert result["github"]["repository"] == REPO
