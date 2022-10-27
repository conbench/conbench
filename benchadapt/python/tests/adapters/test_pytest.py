import json
import tempfile
from pathlib import Path

import pytest

from benchadapt import BenchmarkResult
from benchadapt.adapters import PytestAdapter


PYTEST_BENCHMARK_JSON = {
    "machine_info": {
        "node": "foo.local",
        "processor": "arm",
        "machine": "arm64",
        "python_compiler": "Clang 13.0.1 ",
        "python_implementation": "CPython",
        "python_implementation_version": "3.9.13",
        "python_version": "3.9.13",
        "python_build": ["main", "May 27 2022 17:00:33"],
        "release": "21.6.0",
        "system": "Darwin",
        "cpu": {
            "python_version": "3.9.13.final.0 (64 bit)",
            "cpuinfo_version": [8, 0, 0],
            "cpuinfo_version_string": "8.0.0",
            "arch": "ARM_8",
            "bits": 64,
            "count": 10,
            "arch_string_raw": "arm64",
            "brand_raw": "Apple M3 Pro",
        },
    },
    "commit_info": {
        "id": "0000000000000000000000000000000000000000",
        "time": "2022-10-26T14:50:09-05:00",
        "author_time": "2032-10-26T14:50:09-05:00",
        "dirty": True,
        "project": "conbench",
        "branch": "main",
    },
    "benchmarks": [
        {
            "group": None,
            "name": "test_init",
            "fullname": "tests/adapters/test_pytest.py::test_init",
            "params": None,
            "param": None,
            "extra_info": {},
            "options": {
                "disable_gc": False,
                "timer": "perf_counter",
                "min_rounds": 5,
                "max_time": 1.0,
                "min_time": 5e-06,
                "warmup": False,
            },
            "stats": {
                "min": 1.4000000000014001e-05,
                "max": 0.00022939600000002058,
                "mean": 4.7193749999999145e-05,
                "stddev": 6.79819279176741e-05,
                "rounds": 10,
                "median": 1.5145749999986857e-05,
                "iqr": 4.82505000000133e-05,
                "q1": 1.4353999999994205e-05,
                "q3": 6.26045000000075e-05,
                "iqr_outliers": 1,
                "stddev_outliers": 1,
                "outliers": "1;1",
                "ld15iqr": 1.4000000000014001e-05,
                "hd15iqr": 0.00022939600000002058,
                "ops": 21189.24645742324,
                "total": 0.00047193749999999146,
                "data": [
                    0.00022939600000002058,
                    6.26045000000075e-05,
                    1.5270499999997522e-05,
                    7.602049999999583e-05,
                    1.597949999998516e-05,
                    1.431250000000217e-05,
                    1.4000000000014001e-05,
                    1.49789999999983e-05,
                    1.4353999999994205e-05,
                    1.5020999999976192e-05,
                ],
                "iterations": 2,
            },
        },
        {
            "group": None,
            "name": "test_sleep",
            "fullname": "tests/adapters/test_pytest.py::test_sleep",
            "params": None,
            "param": None,
            "extra_info": {},
            "options": {
                "disable_gc": False,
                "timer": "perf_counter",
                "min_rounds": 5,
                "max_time": 1.0,
                "min_time": 5e-06,
                "warmup": False,
            },
            "stats": {
                "min": 1.0017540415000001,
                "max": 1.0028986665000001,
                "mean": 1.0023990901666666,
                "stddev": 0.0005860147160953284,
                "rounds": 3,
                "median": 1.0025445624999998,
                "iqr": 0.0008584687499999522,
                "q1": 1.00195167175,
                "q3": 1.0028101405,
                "iqr_outliers": 0,
                "stddev_outliers": 1,
                "outliers": "1;0",
                "ld15iqr": 1.0017540415000001,
                "hd15iqr": 1.0028986665000001,
                "ops": 0.9976066516917251,
                "total": 3.0071972705,
                "data": [1.0017540415000001, 1.0025445624999998, 1.0028986665000001],
                "iterations": 2,
            },
        },
    ],
    "datetime": "2022-10-27T19:15:37.605810",
    "version": "4.0.0",
}


# To recreate JSON, `pip install pytest-benchmark`, unquote these two tests and run
# `pytest --benchmark-json='{PATH_TO_STORE_JSON}' benchadapt/python/tests/adapters/test_pytest.py`

# import time

# def test_init(benchmark):
#     def init_pytest_adapter():
#         PytestAdapter(command=["echo", "hello"])

#     benchmark.pedantic(init_pytest_adapter, rounds=10, iterations=2)


# def test_sleep(benchmark):
#     benchmark.pedantic(time.sleep, args=[0.1], rounds=3, iterations=2)


class TestPytestAdapter:
    @pytest.fixture(scope="class")
    def pytest_adapter(self):
        result_file = tempfile.mktemp(suffix=".json")
        pytest_adapter = PytestAdapter(
            command=["echo", "'Hello, world!'"], result_file=Path(result_file)
        )

        with open(pytest_adapter.result_file, "w") as f:
            json.dump(PYTEST_BENCHMARK_JSON, f)

        return pytest_adapter

    def test_transform_results(self, pytest_adapter) -> None:
        results = pytest_adapter.transform_results()

        assert len(results) == 2
        for result in results:
            assert isinstance(result, BenchmarkResult)
            assert result.tags["name"].startswith("tests/adapters/test_pytest.py::")
            assert result.context == {"benchmark_language": "Python"}
            assert "name" in result.tags
            assert result.machine_info is not None
            assert result.stats["iterations"] == len(result.stats["data"])

    def test_run(self, pytest_adapter) -> None:
        results = pytest_adapter.run()
        assert len(results) == 2
