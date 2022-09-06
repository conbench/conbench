import json

import pytest
from conbencher.result import BenchmarkResult
from conbencher.runners import ArcheryRunner

archery_json = {
    "suites": [
        {
            "name": "arrow-tensor-conversion-benchmark",
            "benchmarks": [
                {
                    "name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
                    "unit": "bytes_per_second",
                    "less_is_better": False,
                    "values": [
                        3843659358.727243,
                        3846368103.9123325,
                        3852355319.7965193,
                    ],
                    "time_unit": "ns",
                    "times": [89813.27749444859, 89951.00325321, 90086.37264234325],
                    "counters": {
                        "family_index": 13,
                        "per_family_instance_index": 0,
                        "run_name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
                        "repetitions": 3,
                        "repetition_index": 2,
                        "threads": 1,
                        "iterations": 7691,
                    },
                },
                {
                    "name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCSFTensorInt32",
                    "unit": "bytes_per_second",
                    "less_is_better": False,
                    "values": [906194205.7378266, 921971663.0376312, 922406541.4456899],
                    "time_unit": "ns",
                    "times": [
                        374886.0342104987,
                        375056.96038956096,
                        381894.73465721105,
                    ],
                    "counters": {
                        "family_index": 31,
                        "per_family_instance_index": 0,
                        "run_name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCSFTensorInt32",
                        "repetitions": 3,
                        "repetition_index": 1,
                        "threads": 1,
                        "iterations": 1839,
                    },
                },
            ],
        }
    ]
}


class TestArcheryRunner:
    @pytest.fixture(scope="class")
    def archery_runner(self):
        archery_runner = ArcheryRunner()
        archery_runner.command = ["echo", "'Hello, world!'"]

        with open(archery_runner.result_file, "w") as f:
            json.dump(archery_json, f)

        return archery_runner

    def test_transform_results(self, archery_runner) -> None:
        results = archery_runner.transform_results()

        assert len(results) == len(archery_json["suites"][0]["benchmarks"])
        for result, original in zip(results, archery_json["suites"][0]["benchmarks"]):
            assert isinstance(result, BenchmarkResult)
            assert result.run_name == "DoubleColumnMajorTensorConversionFixture"
            assert result.context == {"benchmark_language": "C++"}
            assert "params" in result.tags
            assert result.machine_info is not None
            assert result.stats["data"] == original["values"]
            assert result.stats["times"] == original["times"]

    def test_run(self, archery_runner) -> None:
        results = archery_runner.run()
        assert len(results) == len(archery_json["suites"][0]["benchmarks"])
